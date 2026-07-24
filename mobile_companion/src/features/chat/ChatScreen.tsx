import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { wsClient } from '../../core/api/WebSocketClient';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  
  // Track the current streaming message
  const currentAssistantMessageId = useRef<string | null>(null);

  useEffect(() => {
    const unsubscribe = wsClient.subscribeToMessages((msg) => {
      if (msg.type === 'assistant_text') {
        setIsTyping(true);
        const textDelta = msg.delta || '';
        
        setMessages((prev) => {
          const newMessages = [...prev];
          
          if (!currentAssistantMessageId.current) {
            // New message starting
            currentAssistantMessageId.current = Date.now().toString();
            newMessages.push({
              id: currentAssistantMessageId.current,
              role: 'assistant',
              text: textDelta
            });
          } else {
            // Append to existing message
            const lastMsgIndex = newMessages.findIndex(m => m.id === currentAssistantMessageId.current);
            if (lastMsgIndex !== -1) {
              newMessages[lastMsgIndex].text += textDelta;
            }
          }
          return newMessages;
        });
      } else if (msg.type === 'assistant_text_end' || msg.type === 'playback_complete') {
        setIsTyping(false);
        currentAssistantMessageId.current = null;
      } else if (msg.type === 'error') {
        setIsTyping(false);
        currentAssistantMessageId.current = null;
      }
    });

    return () => unsubscribe();
  }, []);

  const sendMessage = () => {
    if (!inputText.trim()) return;
    
    // Add user message to UI immediately
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      text: inputText.trim(),
    };
    setMessages((prev) => [...prev, userMsg]);
    
    // Send via WebSocket
    wsClient.send({ type: 'text', text: inputText.trim() });
    
    setInputText('');
    setIsTyping(true);
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container} 
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView 
        ref={scrollViewRef}
        style={styles.chatContainer}
        contentContainerStyle={styles.chatContent}
        onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.map((msg) => (
          <View 
            key={msg.id} 
            style={[
              styles.messageBubble, 
              msg.role === 'user' ? styles.userBubble : styles.assistantBubble
            ]}
          >
            <Text style={styles.messageText}>{msg.text}</Text>
          </View>
        ))}
        {isTyping && (
          <View style={[styles.messageBubble, styles.assistantBubble, styles.typingBubble]}>
            <Text style={styles.typingText}>Genie is typing...</Text>
          </View>
        )}
      </ScrollView>

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Ask Genie..."
          placeholderTextColor="#94A3B8"
          onSubmitEditing={sendMessage}
        />
        <TouchableOpacity style={styles.sendButton} onPress={sendMessage}>
          <Text style={styles.sendButtonText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  chatContainer: {
    flex: 1,
  },
  chatContent: {
    padding: 16,
    paddingBottom: 32,
  },
  messageBubble: {
    maxWidth: '80%',
    padding: 16,
    borderRadius: 16,
    marginBottom: 12,
  },
  userBubble: {
    backgroundColor: '#3B82F6',
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: '#1E293B',
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#334155',
  },
  typingBubble: {
    padding: 12,
  },
  messageText: {
    color: '#F8FAFC',
    fontSize: 16,
    lineHeight: 24,
  },
  typingText: {
    color: '#94A3B8',
    fontSize: 14,
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#1E293B',
    borderTopWidth: 1,
    borderTopColor: '#334155',
    alignItems: 'center',
  },
  textInput: {
    flex: 1,
    backgroundColor: '#0F172A',
    color: '#F8FAFC',
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sendButton: {
    marginLeft: 12,
    backgroundColor: '#3B82F6',
    borderRadius: 24,
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  sendButtonText: {
    color: '#FFF',
    fontWeight: 'bold',
    fontSize: 16,
  }
});
