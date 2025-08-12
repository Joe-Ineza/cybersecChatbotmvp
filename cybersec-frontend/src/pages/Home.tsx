import React from 'react';
import ChatWindow from '../components/ChatWindow';

const Home: React.FC = () => {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
            <h1 className="text-4xl font-bold mb-4">Welcome to CyberMentor</h1>
            <p className="text-lg mb-8">Your AI-powered cybersecurity assistant.</p>
            <ChatWindow />
        </div>
    );
};

export default Home;