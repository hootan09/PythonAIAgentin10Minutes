import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, FlatList } from 'react-native';

const WS_URL = 'ws://YOUR_COMPUTER_IP:8765'; // same network

export default function App() {
  const [ws, setWs] = useState(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const socket = new WebSocket(WS_URL);
    socket.onopen = () => console.log('connected');
    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      setMessages((m) => [...m, { who: 'agent', text: msg.text }]);
    };
    socket.onerror = (e) => console.error(e);
    setWs(socket);
    return () => socket.close();
  }, []);

  const send = () => {
    if (!input.trim() || !ws) return;
    ws.send(JSON.stringify({ text: input }));
    setMessages((m) => [...m, { who: 'user', text: input }]);
    setInput('');
  };

  return (
    <View style={{ flex: 1, padding: 20 }}>
      <FlatList
        data={messages}
        keyExtractor={(_, i) => i.toString()}
        renderItem={({ item }) => (
          <Text style={{ fontWeight: item.who === 'user' ? 'bold' : 'normal' }}>
            {item.who}: {item.text}
          </Text>
        )}
      />
      <TextInput
        value={input}
        onChangeText={setInput}
        placeholder="Ask DataGen…"
        style={{ borderWidth: 1, marginVertical: 10 }}
      />
      <Button title="Send" onPress={send} />
    </View>
  );
}