import os
import threading
import urllib.request
import re

try:
    import sounddevice as sd
    import numpy as np
    HAS_TTS_DEPS = True
except ImportError:
    HAS_TTS_DEPS = False

# piper sera importé dynamiquement pour éviter les erreurs si installé à chaud

VOICES_DIR = "voices"

# Voix française par défaut (qualité medium, très bon compromis)
DEFAULT_VOICE_URL_ONNX = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx?download=true"
DEFAULT_VOICE_URL_JSON = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/upmc/medium/fr_FR-upmc-medium.onnx.json?download=true"

class TTSManager:
    def __init__(self):
        if not HAS_TTS_DEPS:
            raise ImportError("Dépendances manquantes pour TTS (sounddevice, numpy).")
        self.voices_dir = VOICES_DIR
        if not os.path.exists(self.voices_dir):
            os.makedirs(self.voices_dir)
            
        self.available_voices = self._scan_voices()
        self.current_voice_name = None
        self.voice = None
        self.is_playing = False
        self.current_session = 0
        self.stream = None
        self.lock = threading.RLock()
        self.volume = 0.5  # Volume par défaut à 50%
        
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
        """Arrête la lecture en cours en incrémentant la session et en abortant le flux."""
        with self.lock:
            self.is_playing = False
            self.current_session += 1
            if self.stream:
                try:
                    # abort() est plus radical que stop(), il coupe immédiatement
                    self.stream.abort()
                except Exception:
                    pass
                self.stream = None

    def speak(self, text, on_start=None, on_finish=None):
        """Lit un texte à voix haute en streaming avec gestion de session."""
        # Nettoyage des émojis du texte pour éviter qu'ils ne soient prononcés par le moteur de synthèse
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27BF]|[\u200d\ufe0f\ufe0e]')
        cleaned_text = emoji_pattern.sub('', text)
        # Retrait des astérisques (utilisés pour le formatage markdown comme le gras ou l'italique)
        cleaned_text = cleaned_text.replace('*', '')
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        if not self.voice or not cleaned_text:
            print("[TTS_MANAGER] Pas de voix chargée ou texte vide après nettoyage.")
            if on_finish: on_finish()
            return
            
        # Arrêter toute lecture en cours et démarrer une nouvelle session
        # On utilise un lock pour s'assurer que l'incrément de session et le flag sont atomiques
        with self.lock:
            self.stop()
            self.is_playing = True
            session_id = self.current_session
        
        def _speak_thread():
            try:
                if on_start: on_start()
                
                sample_rate = self.voice.config.sample_rate
                # Utiliser sounddevice avec un gestionnaire de contexte pour plus de sécurité
                with sd.OutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                    self.stream = stream
                    stream.start()
                    
                    # Piper génère l'audio par petits morceaux (streaming)
                    for chunk in self.voice.synthesize(cleaned_text):
                        # Couper prématurément si demandé ou si une nouvelle session a démarré
                        if not self.is_playing or session_id != self.current_session:
                            break 
                        
                        # Découper l'audio en petits segments (100ms) pour pouvoir l'interrompre instantanément
                        audio_data = chunk.audio_int16_array
                        chunk_size = int(sample_rate * 0.1)
                        
                        for i in range(0, len(audio_data), chunk_size):
                            if not self.is_playing or session_id != self.current_session:
                                break 
                            
                            try:
                                segment = audio_data[i:i+chunk_size]
                                if self.volume != 1.0:
                                    segment = (segment * self.volume).astype(np.int16)
                                stream.write(segment)
                            except Exception:
                                # Souvent causé par un abort() volontaire
                                break
            except Exception as e:
                print(f"[TTS_MANAGER] Erreur lecture TTS: {e}")
            finally:
                self.stream = None
                # On ne réinitialise is_playing et on n'appelle on_finish 
                # que si c'est toujours notre session qui est active
                if session_id == self.current_session:
                    self.is_playing = False
                    if on_finish: on_finish()

        threading.Thread(target=_speak_thread, daemon=True).start()
