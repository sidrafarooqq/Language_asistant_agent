"use client";
import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { motion } from "framer-motion";

interface Message {
  id: number;
  text: string;
  fromUser: boolean;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "https://languageasistantagent-production.up.railway.app/";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const toHistory = (msgs: Message[]) =>
    msgs.map(({ fromUser, text }) => ({
      role: fromUser ? "user" : "assistant",
      content: text,
    }));

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim()) return;

    const userMsg: Message = { id: Date.now(), text: input, fromUser: true };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: toHistory([...messages, userMsg]),
          user_input: input,
        }),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      const botMsg: Message = {
        id: Date.now() + 1,
        text: data.assistant_reply,
        fromUser: false,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 2, text: `🚨 Error: ${err.message}`, fromUser: false },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  return (
    <div
      className="relative min-h-screen bg-[url('/abstract-background-design-images-wallpaper-ai-generated_643360-262414.jpg')] bg-cover bg-center bg-no-repeat flex items-center justify-center px-4 py-8"
    >
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm z-0" />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center w-full space-y-6">
        {/* Heading */}
        <h1 className="text-4xl font-extrabold text-white drop-shadow-lg text-center tracking-wide">
          📚 Language Learning Assistant
        </h1>

        {/* Chat container */}
        <div className="w-full max-w-2xl h-[80vh] bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl flex flex-col overflow-hidden border border-gray-200">

          {/* Messages */}
          <div
            ref={containerRef}
            className="flex-1 overflow-y-auto px-6 py-4 space-y-3 scrollbar-thin scrollbar-thumb-blue-300 scrollbar-track-transparent"
          >
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 200, damping: 20 }}
                className={`max-w-[80%] px-4 py-2 text-sm rounded-xl shadow
                  ${
                    msg.fromUser
                      ? "bg-black text-white ml-auto text-right"
                      : "bg-gray-100 text-gray-900 mr-auto text-left"
                  }`}
              >
                {msg.text}
              </motion.div>
            ))}

            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-sm text-gray-500 bg-gray-100 px-4 py-2 rounded-xl w-fit"
              >
                Typing...
              </motion.div>
            )}
          </div>

          {/* Input form */}
          <form
            onSubmit={handleSend}
            className="flex items-center gap-2 p-4 border-t border-gray-200 bg-white/60"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              className="flex-1 px-4 py-2 rounded-full bg-zinc-400 border-black border-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-black hover:from-blue-600 hover:to-indigo-700 text-white p-2 rounded-full transition-all disabled:opacity-50"
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
