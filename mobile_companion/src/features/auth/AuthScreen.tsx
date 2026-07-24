import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { Camera, CameraView } from 'expo-camera';
import { connectionManager } from '../../core/network/ConnectionManager';
import { secureStorage } from '../../core/storage/SecureStorage';
import { wsClient } from '../../core/api/WebSocketClient';

export default function AuthScreen({ onLoginSuccess }: { onLoginSuccess: () => void }) {
  const [url, setUrl] = useState('');
  const [pin, setPin] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    (async () => {
      const { status } = await Camera.requestCameraPermissionsAsync();
      setHasPermission(status === 'granted');
      
      // Auto-fill from secure storage
      const savedUrl = await secureStorage.getServerUrl();
      const savedPin = await secureStorage.getPin();
      if (savedUrl) setUrl(savedUrl);
      if (savedPin) setPin(savedPin);
    })();
  }, []);

  const handleConnect = async () => {
    if (!url || !pin) {
      Alert.alert('Error', 'Please enter both Server URL and PIN.');
      return;
    }

    setIsLoading(true);
    try {
      // 1. Validate REST connection
      let method: 'cloudflare' | 'local' | 'tailscale' | 'ngrok' | 'custom' = 'custom';
      if (url.includes('trycloudflare.com')) method = 'cloudflare';
      else if (url.includes('192.168.') || url.includes('10.')) method = 'local';
      else if (url.includes('tailscale') || url.includes('100.')) method = 'tailscale';
      else if (url.includes('ngrok')) method = 'ngrok';

      const isConnected = await connectionManager.validateAndConnect(url, method);
      
      if (isConnected) {
        // 2. Establish WebSocket connection with PIN
        const currentConn = connectionManager.getCurrentConnection();
        if (currentConn) {
          await secureStorage.saveServerUrl(currentConn.url);
          await secureStorage.savePin(pin);
          
          wsClient.connect(currentConn.url, pin);
          
          // Wait for auth_ok or auth_fail
          const unsubscribe = wsClient.subscribeToStatus((status) => {
            if (status === 'connected') {
              setIsLoading(false);
              unsubscribe();
              onLoginSuccess();
            } else if (status === 'auth_failed') {
              setIsLoading(false);
              unsubscribe();
              Alert.alert('Authentication Failed', 'Invalid PIN provided.');
            } else if (status === 'error') {
              setIsLoading(false);
              unsubscribe();
              Alert.alert('Connection Error', 'Failed to connect to the WebSocket server.');
            }
          });
        }
      } else {
        setIsLoading(false);
        Alert.alert('Connection Failed', 'Could not reach the Genie Server at the provided URL.');
      }
    } catch (error) {
      setIsLoading(false);
      Alert.alert('Error', 'An unexpected error occurred.');
    }
  };

  const handleBarcodeScanned = ({ type, data }: { type: string, data: string }) => {
    setIsScanning(false);
    try {
      // Expected QR format: {"url": "https://...", "pin": "1234"}
      const parsed = JSON.parse(data);
      if (parsed.url) setUrl(parsed.url);
      if (parsed.pin) setPin(parsed.pin);
      
      if (parsed.url && parsed.pin) {
        Alert.alert('QR Scanned', 'Configuration loaded successfully!');
      } else {
        Alert.alert('Invalid QR Code', 'The QR code does not contain valid Genie connection data.');
      }
    } catch (e) {
      Alert.alert('Invalid QR Code', 'Failed to parse the QR code data.');
    }
  };

  if (isScanning) {
    if (hasPermission === null) {
      return <View style={styles.container}><Text>Requesting camera permission...</Text></View>;
    }
    if (hasPermission === false) {
      return <View style={styles.container}><Text>No access to camera</Text></View>;
    }
    return (
      <View style={styles.container}>
        <CameraView
          onBarcodeScanned={handleBarcodeScanned}
          barcodeScannerSettings={{
            barcodeTypes: ["qr"],
          }}
          style={StyleSheet.absoluteFillObject}
        />
        <TouchableOpacity style={styles.cancelScanButton} onPress={() => setIsScanning(false)}>
          <Text style={styles.cancelScanText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Connect to Genie</Text>
      
      <View style={styles.inputContainer}>
        <Text style={styles.label}>Server URL</Text>
        <TextInput
          style={styles.input}
          placeholder="https://xxxxx.trycloudflare.com"
          value={url}
          onChangeText={setUrl}
          autoCapitalize="none"
          keyboardType="url"
        />
      </View>

      <View style={styles.inputContainer}>
        <Text style={styles.label}>API PIN</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter 4-6 digit PIN"
          value={pin}
          onChangeText={setPin}
          secureTextEntry
          keyboardType="numeric"
        />
      </View>

      <TouchableOpacity 
        style={[styles.button, styles.primaryButton, isLoading && styles.disabledButton]} 
        onPress={handleConnect}
        disabled={isLoading}
      >
        {isLoading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Connect</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity 
        style={[styles.button, styles.secondaryButton]} 
        onPress={() => setIsScanning(true)}
        disabled={isLoading}
      >
        <Text style={styles.secondaryButtonText}>Scan QR Code</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
    padding: 24,
    justifyContent: 'center',
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 48,
    textAlign: 'center',
  },
  inputContainer: {
    marginBottom: 24,
  },
  label: {
    color: '#94A3B8',
    marginBottom: 8,
    fontSize: 14,
    fontWeight: '600',
  },
  input: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 16,
    color: '#F8FAFC',
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  button: {
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 16,
  },
  primaryButton: {
    backgroundColor: '#3B82F6',
    marginTop: 24,
  },
  disabledButton: {
    backgroundColor: '#2563EB',
    opacity: 0.7,
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  secondaryButtonText: {
    color: '#3B82F6',
    fontSize: 16,
    fontWeight: 'bold',
  },
  cancelScanButton: {
    position: 'absolute',
    bottom: 50,
    alignSelf: 'center',
    backgroundColor: 'rgba(0,0,0,0.7)',
    padding: 16,
    borderRadius: 30,
  },
  cancelScanText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  }
});
