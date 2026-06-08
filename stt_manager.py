try:
    import sounddevice as sd
    import numpy as np
    from faster_whisper import WhisperModel
    HAS_STT_DEPS = True
except ImportError:
    HAS_STT_DEPS = False

import wave
import threading
import os
import queue

class STTManager:
    def __init__(self, on_model_ready=None, on_model_error=None, 
                 silence_threshold=0.015, silence_duration_limit=0.8, 
                 pre_roll_duration=0.3, min_phrase_duration=0.3):
        if not HAS_STT_DEPS:
            raise ImportError("Dépendances manquantes pour STT (sounddevice, numpy, faster-whisper).")
        # États du modèle
        self.is_model_loading = False
        self.is_model_ready = False
        self.model_load_error = None
        self.model = None
        
        # États d'enregistrement
        self.is_recording = False
        self.audio_data = []
        self.sample_rate = 16000
        self.stream = None
        
        # Configurations VAD
        self.silence_threshold = silence_threshold
        self.silence_duration_limit = silence_duration_limit
        self.pre_roll_duration = pre_roll_duration
        self.min_phrase_duration = min_phrase_duration
        
        # États de concurrence et de contrôle
        self.lock = threading.Lock()
        self.active_transcriptions = 0
        self.all_done_called = False
        
        # Callbacks pour la GUI
        self.on_model_ready = on_model_ready
        self.on_model_error = on_model_error
        self.on_phrase_transcribed = None
        self.on_all_done = None
        
        # Lancer le chargement du modèle immédiatement
        self._load_model_in_background()

    def _load_model_in_background(self):
        """Lance le chargement du modèle Whisper dans un thread séparé."""
        self.is_model_loading = True
        threading.Thread(target=self._load_model_thread, daemon=True).start()

    def _load_model_thread(self):
        """Thread de chargement du modèle."""
        try:
            # On utilise le modèle "tiny" pour plus de rapidité en local
            # compute_type="int8" permet de réduire l'utilisation de la RAM
            self.model = WhisperModel("tiny", device="cpu", compute_type="int8")
            
            self.is_model_loading = False
            self.is_model_ready = True
            
            if self.on_model_ready:
                self.on_model_ready()
                
        except Exception as e:
            self.is_model_loading = False
            self.model_load_error = str(e)
            print(f"[STT_MANAGER] Erreur chargement modèle : {e}")
            if self.on_model_error:
                self.on_model_error(str(e))

    def start_recording(self, on_phrase_transcribed=None, on_all_done=None):
        """Démarre la capture audio depuis le micro en mode streaming."""
        if not self.is_model_ready:
            return False, "Le modèle n'est pas encore prêt."
        if self.is_recording:
            return False, "Enregistrement déjà en cours."
            
        self.on_phrase_transcribed = on_phrase_transcribed
        self.on_all_done = on_all_done
        self.is_recording = True
        self.all_done_called = False
        self.active_transcriptions = 0
        
        self.audio_queue = queue.Queue()
        self.current_phrase_audio = []
        
        # Calcul des tailles en échantillons
        self.pre_roll_max_len = int(self.sample_rate * self.pre_roll_duration)
        self.silence_limit_samples = int(self.sample_rate * self.silence_duration_limit)
        self.min_phrase_samples = int(self.sample_rate * self.min_phrase_duration)
        
        # États de suivi VAD
        self.pre_roll_buffer = []
        self.has_speech = False
        self.silence_samples = 0
        
        def callback(indata, frames, time, status):
            if status:
                print(f"[STT_MANAGER] Attention audio: {status}")
            if self.is_recording:
                self.audio_queue.put(indata.copy())

        try:
            # Enregistrement en mono (channels=1)
            self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback)
            self.stream.start()
            
            # Lancer le thread worker de traitement
            self.worker_thread = threading.Thread(target=self._recording_worker, daemon=True)
            self.worker_thread.start()
            
            return True, "Enregistrement démarré."
        except Exception as e:
            self.is_recording = False
            return False, f"Erreur lors de l'accès au micro : {str(e)}"

    def _recording_worker(self):
        """Thread worker traitant le flux audio et détectant les pauses (VAD)."""
        while self.is_recording or not self.audio_queue.empty():
            try:
                block = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
                
            samples = block.flatten()
            if len(samples) == 0:
                continue
                
            # Calcul de l'énergie efficace (RMS)
            rms = np.sqrt(np.mean(samples**2))
            
            if rms > self.silence_threshold:
                if not self.has_speech:
                    # Début de parole : préfixer avec le pre-roll
                    if self.pre_roll_buffer:
                        self.current_phrase_audio.extend(self.pre_roll_buffer)
                        self.pre_roll_buffer = []
                    self.has_speech = True
                
                self.current_phrase_audio.extend(samples)
                self.silence_samples = 0
            else:
                # Silence
                if self.has_speech:
                    self.current_phrase_audio.extend(samples)
                    self.silence_samples += len(samples)
                    
                    if self.silence_samples >= self.silence_limit_samples:
                        # Pause détectée ! Finaliser et transcrire le segment accumulé
                        # Soustraire le silence de la fin de l'audio pour éviter d'envoyer trop de silence à Whisper
                        audio_to_transcribe = self.current_phrase_audio[:-self.silence_samples]
                        if len(audio_to_transcribe) >= self.min_phrase_samples:
                            self._trigger_phrase_transcription(audio_to_transcribe)
                        
                        self.current_phrase_audio = []
                        self.has_speech = False
                        self.silence_samples = 0
                else:
                    # Accumulation du pre-roll circulaire
                    self.pre_roll_buffer.extend(samples)
                    if len(self.pre_roll_buffer) > self.pre_roll_max_len:
                        self.pre_roll_buffer = self.pre_roll_buffer[-self.pre_roll_max_len:]

    def _trigger_phrase_transcription(self, audio_samples):
        """Lance un thread pour transcrire le segment audio donné."""
        audio_np = np.array(audio_samples, dtype=np.float32)
        with self.lock:
            self.active_transcriptions += 1
            
        threading.Thread(
            target=self._transcribe_phrase_thread,
            args=(audio_np,),
            daemon=True
        ).start()

    def _transcribe_phrase_thread(self, audio_np):
        """Effectue la transcription asynchrone en mémoire et notifie la GUI."""
        try:
            # Écrêter l'audio pour éviter les distorsions
            audio_np = np.clip(audio_np, -1.0, 1.0)
            
            # Transcription directe via faster-whisper en passant le numpy array
            segments, info = self.model.transcribe(audio_np, beam_size=5, language="fr")
            text = " ".join([segment.text for segment in segments]).strip()
            
            if text and self.on_phrase_transcribed:
                self.on_phrase_transcribed(text)
                
        except Exception as e:
            print(f"[STT_MANAGER] Erreur de transcription en tâche de fond : {e}")
        finally:
            with self.lock:
                self.active_transcriptions -= 1
            self._maybe_call_all_done()

    def _maybe_call_all_done(self):
        """Méthode interne thread-safe appelant le callback on_all_done."""
        call_callback = False
        with self.lock:
            if not self.is_recording and self.active_transcriptions == 0 and not self.all_done_called:
                self.all_done_called = True
                call_callback = True
                
        if call_callback and self.on_all_done:
            self.on_all_done()

    def stop_recording(self):
        """Arrête l'enregistrement et force le traitement de l'audio résiduel."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        # [Stratégie 1] Attendre la fin complète du thread worker
        if hasattr(self, 'worker_thread'):
            self.worker_thread.join(timeout=1.0)
            
        # Traiter l'audio restant après la fin du thread worker
        if self.has_speech and self.current_phrase_audio:
            # Retirer le silence éventuel à la fin
            audio_to_transcribe = self.current_phrase_audio
            if self.silence_samples > 0:
                audio_to_transcribe = self.current_phrase_audio[:-self.silence_samples]
                
            if len(audio_to_transcribe) >= self.min_phrase_samples:
                self._trigger_phrase_transcription(audio_to_transcribe)
                
        self.current_phrase_audio = []
        self.pre_roll_buffer = []
        self.has_speech = False
        
        # Vérifier si on peut déjà appeler on_all_done
        self._maybe_call_all_done()
