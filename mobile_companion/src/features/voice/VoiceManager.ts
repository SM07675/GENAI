import { Audio } from 'expo-av';
import { wsClient } from '../../core/api/WebSocketClient';

class VoiceManager {
  private recording: Audio.Recording | null = null;
  private isRecording = false;

  async requestPermissions() {
    try {
      const permission = await Audio.requestPermissionsAsync();
      return permission.status === 'granted';
    } catch (e) {
      console.error('[VoiceManager] Failed to request permissions', e);
      return false;
    }
  }

  async startRecording() {
    if (this.isRecording) return;
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      console.log('[VoiceManager] Starting recording...');
      const { recording } = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      this.recording = recording;
      this.isRecording = true;

      // Notify backend that voice is starting (if using continuous mode)
      wsClient.send({ type: 'voice_start' });
    } catch (err) {
      console.error('[VoiceManager] Failed to start recording', err);
    }
  }

  async stopRecordingAndSend() {
    if (!this.recording || !this.isRecording) return;

    try {
      console.log('[VoiceManager] Stopping recording...');
      await this.recording.stopAndUnloadAsync();
      const uri = this.recording.getURI();
      this.isRecording = false;
      this.recording = null;

      if (uri) {
        console.log(`[VoiceManager] Audio saved at ${uri}`);
        
        // In a production app, we would stream PCM data directly or upload the file
        // Due to platform limitations in this boilerplate, we'll notify the backend
        // that voice input was captured. To actually send raw PCM, we would need 
        // a native module or WebRTC, which requires a custom dev client.
        
        // Example mock payload to the backend:
        wsClient.send({ 
          type: 'audio_end', 
          message: 'Voice recorded from mobile device.' 
        });
      }
    } catch (err) {
      console.error('[VoiceManager] Failed to stop recording', err);
    }
  }
}

export const voiceManager = new VoiceManager();
