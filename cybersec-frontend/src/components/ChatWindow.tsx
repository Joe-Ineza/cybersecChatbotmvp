import React, { useState } from 'react';

const ChatWindow: React.FC = () => {
    const [message, setMessage] = useState('');
    const [chatHistory, setChatHistory] = useState<{ user: string; bot: string }[]>([]);

    const handleSendMessage = async () => {
        if (!message.trim()) return;

        const userMessage = { user: message, bot: '' };
        setChatHistory([...chatHistory, userMessage]);
        setMessage('');

        try {
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message }),
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            const botMessage = { user: 'Bot', bot: data.response };
            setChatHistory((prev) => [...prev, botMessage]);
        } catch (error) {
            console.error('Error sending message:', error);
        }
    };

    return (
        <div className="flex flex-col h-full p-4 border rounded-lg shadow-lg">
            <div className="flex-1 overflow-y-auto">
                {chatHistory.map((entry, index) => (
                    <div key={index} className="mb-2">
                        <div className="font-bold">{entry.user}:</div>
                        <div>{entry.bot}</div>
                    </div>
                ))}
            </div>
            <div className="flex mt-4">
                <input
                    type="text"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="flex-1 p-2 border rounded-l-lg"
                    placeholder="Type your message..."
                />
                <button
                    onClick={handleSendMessage}
                    className="p-2 bg-blue-500 text-white rounded-r-lg"
                >
                    Send
                </button>
            </div>
        </div>
    );
};

export default ChatWindow;