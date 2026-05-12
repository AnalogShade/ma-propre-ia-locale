import os
import threading
import urllib.request
import sounddevice as sd
import numpy as np

# piper sera importé dynamiquement pour éviter les erreurs si installé à chaud

VOICES_DIR = "voices"

# Voix française par défaut (qualité medium, très bon compromis)
DEFAULT_VOICE_URL_ONNX = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx?download=true"
DEFAULT_VOICE_URL_JSON = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx.json?download=true"

class TTSManager:
    def __init__(self):
        self.voices_dir = VOICES_DIR
        if not os.path.exists(self.voices_dir):
            os.makedirs(self.voices_dir)
            
        self.available_voices = self._scan_voices()
        self.current_voice_name = None
        self.voice = None
        self.is_playing = False
        
        # Charger la première voix disponible par défaut
        if self.available_voices:
            self.load_voice(self.available_voices[0])

    def _scan_voices(self):
        """Scanne le dossier local à la recherche de modèles Piper."""
        voices = []
        if os.path.exists(self.voices_dir):
            for file in os.listdir(self.voices_dir):
                if file.endswith(".onnx"):
                    name = file[:-5]
                    # Vérifier si le fichier config JSON existe aussi
                    if os.path.exists(os.path.join(self.voices_dir, f"{file}.json")):
                        voices.append(name)
        return voices

    def download_default_voice(self, on_progress=None):
        """Télécharge une voix française par défaut depuis HuggingFace."""
        def _download():
            try:
                if on_progress: on_progress("Téléchargement modèle...")
                onnx_path = os.path.join(self.voices_dir, "fr_FR-upmc-medium.onnx")
                json_path = os.path.join(self.voices_dir, "fr_FR-upmc-medium.onnx.json")
                
                urllib.request.urlretrieve(DEFAULT_VOICE_URL_ONNX, onnx_path)
                if on_progress: on_progress("Téléchargement config...")
                urllib.request.urlretrieve(DEFAULT_VOICE_URL_JSON, json_path)
                
                self.available_voices = self._scan_voices()
                if self.available_voices:
                    self.load_voice("fr_FR-upmc-medium")
                    
                if on_progress: on_progress("Voix prête.")
            except Exception as e:
                print(f"[TTS_MANAGER] Erreur téléchargement voix: {e}")
                if on_progress: on_progress("Erreur DL.")
        
        threading.Thread(target=_download, daemon=True).start()

    def get_voices(self):
        return self.available_voices

    def load_voice(self, voice_name):
        """Charge le modèle Piper en mémoire."""
        try:
            from piper.voice import PiperVoice
        except Exception as e:
            print(f"[TTS_MANAGER] piper-tts n'est pas accessible : {e}")
            self.voice = None
            return False
            
        onnx_path = os.path.join(self.voices_dir, f"{voice_name}.onnx")
        json_path = os.path.join(self.voices_dir, f"{voice_name}.onnx.json")
        
        if not os.path.exists(onnx_path) or not os.path.exists(json_path):
            return False
            
        try:
            self.voice = PiperVoice.load(onnx_path, config_path=json_path)
            self.current_voice_name = voice_name
            print(f"[TTS_MANAGER] Voix {voice_name} chargée.")
            return True
        except Exception as e:
            print(f"[TTS_MANAGER] Erreur chargement voix {voice_name}: {e}")
            return False

    def stop(self):
        """Arrête la lecture en cours."""
        self.is_playing = False

    def speak(self, text, on_start=None, on_finish=None):
        """Lit un texte à voix haute en streaming."""
        if not self.voice or not text.strip():
            print("[TTS_MANAGER] Pas de voix chargée ou texte vide.")
            if on_finish: on_finish()
            return
            
        # Si déjà en cours, on coupe
        if self.is_playing:
            self.stop()
            import time
            time.sleep(0.2) # Laisser le temps au flux précédent de s'arrêter
            
        self.is_playing = True
        
        def _speak_thread():
            try:
                if on_start: on_start()
                
                sample_rate = self.voice.config.sample_rate
                # Démarrer le flux audio avec sounddevice
                stream = sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16')
                stream.start()
                
                # Piper génère l'audio par petits morceaux (streaming)
                for chunk in self.voice.synthesize(text):
                    if not self.is_playing:
                        break # Couper prématurément si demandé
                    
                    # chunk.audio_int16_array est un numpy.ndarray
                    stream.write(chunk.audio_int16_array)
                    
                stream.stop()
                stream.close()
            except Exception as e:
                print(f"[TTS_MANAGER] Erreur lecture TTS: {e}")
            finally:
                self.is_playing = False
                if on_finish: on_finish()

        threading.Thread(target=_speak_thread, daemon=True).start()
