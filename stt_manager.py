import sounddevice as sd
import numpy as np
import wave
from faster_whisper import WhisperModel
import threading
import os

class STTManager:
    def __init__(self, on_model_ready=None, on_model_error=None):
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
        
        # Callbacks pour la GUI
        self.on_model_ready = on_model_ready
        self.on_model_error = on_model_error
        
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

    def start_recording(self):
        """Démarre la capture audio depuis le micro."""
        if not self.is_model_ready:
            return False, "Le modèle n'est pas encore prêt."
        if self.is_recording:
            return False, "Enregistrement déjà en cours."
            
        self.audio_data = []
        self.is_recording = True
        
        def callback(indata, frames, time, status):
            if status:
                print(f"[STT_MANAGER] Attention audio: {status}")
            self.audio_data.append(indata.copy())

        try:
            # Enregistrement en mono (channels=1)
            self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback)
            self.stream.start()
            return True, "Enregistrement démarré."
        except Exception as e:
            self.is_recording = False
            return False, f"Erreur lors de l'accès au micro : {str(e)}"

    def stop_recording_and_transcribe(self, on_transcription_done):
        """Arrête l'enregistrement et lance la transcription asynchrone."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            on_transcription_done("")
            return

        # Concaténer tous les blocs audio capturés
        audio_np = np.concatenate(self.audio_data, axis=0)
        
        # Lancer la transcription dans un thread séparé pour ne pas geler la GUI
        threading.Thread(
            target=self._transcribe_thread, 
            args=(audio_np, on_transcription_done), 
            daemon=True
        ).start()

    def _transcribe_thread(self, audio_np, on_transcription_done):
        """Thread effectuant l'écriture du WAV et la transcription."""
        temp_file = "data/temp_recording.wav"
        try:
            # Convertir le numpy array (float32) en int16 pour le fichier WAV en s\u00e9curisant les d\u00e9passements
            audio_np = np.clip(audio_np, -1.0, 1.0)
            audio_int16 = (audio_np * 32767).astype(np.int16)
            
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 2 octets = 16 bits
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_int16.tobytes())

            # Transcription via faster-whisper
            segments, info = self.model.transcribe(temp_file, beam_size=5, language="fr")
            
            # Recomposer le texte
            text = " ".join([segment.text for segment in segments])
            
            # Nettoyage du fichier temporaire
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            on_transcription_done(text.strip())
            
        except Exception as e:
            print(f"[STT_MANAGER] Erreur de transcription: {e}")
            on_transcription_done("")
