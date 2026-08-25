"use client";

import { useState, useRef, useEffect, type FormEvent } from "react";
import { Bot, MessageSquare, UserRound, X, Send, Maximize2, Minimize2, Mic, Pause, Play, Square, Trash2 } from "lucide-react";
import styles from "./AIAssistant.module.css";
import { API_URL as ASSISTANT_API_URL } from "@/lib/api";
import voiceStyles from "./VoiceRecording.module.css";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date | null;
};

const SHOPY_LOGO = "/images/brand/shopy-logo-transparent.png";

export default function AIAssistant() {
  const [isHovered, setIsHovered] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello! 👋 I'm Shopy's AI Assistant. I can help you find products, track orders, or explore deals.",
      timestamp: null,
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [voiceState, setVoiceState] = useState<"idle" | "recording" | "preview" | "transcribing">("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [recordingBlob, setRecordingBlob] = useState<Blob | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [recordingError, setRecordingError] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatRef = useRef<HTMLElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const closeAssistantRef = useRef<() => void>(() => {});
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const transcriptionAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (voiceState !== "recording") return;
    const interval = window.setInterval(() => setRecordingSeconds((seconds) => seconds + 1), 1000);
    return () => window.clearInterval(interval);
  }, [voiceState]);

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  useEffect(() => () => {
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    transcriptionAbortRef.current?.abort();
  }, []);

  const requestAssistantReply = async (history: Message[]) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${ASSISTANT_API_URL}/api/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.slice(-12).map((message) => ({
            role: message.role,
            content: message.content,
          })),
        }),
      });
      const data = await response.json() as { reply?: string; detail?: string };
      const reply = data.reply;
      if (!response.ok || !reply) throw new Error(data.detail ?? "No response received.");
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${prev.length + 1}`,
          role: "assistant",
          content: reply,
          timestamp: new Date(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${prev.length + 1}`,
          role: "assistant",
          content: "I’m unable to connect right now. Please check that the Shopy AI service is running and try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const sendTextMessage = (content: string) => {
    if (!content.trim()) return;

    const userMessage: Message = {
      id: `user-${messages.length + 1}`,
      role: "user",
      content: content.trim(),
      timestamp: new Date(),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    void requestAssistantReply(nextMessages);
  };

  const handleSendMessage = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendTextMessage(input);
    setInput("");
  };

  const formatTime = (timestamp: Date) =>
    timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const formatDuration = (seconds: number) => `${Math.floor(seconds / 60)}:${(seconds % 60).toString().padStart(2, "0")}`;

  const stopStream = () => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setRecordingError("Voice recording is not supported in this browser.");
      return;
    }

    try {
      setRecordingError("");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredMimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((mimeType) => MediaRecorder.isTypeSupported(mimeType));
      const recorder = preferredMimeType ? new MediaRecorder(stream, { mimeType: preferredMimeType }) : new MediaRecorder(stream);
      const chunks: BlobPart[] = [];

      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        stopStream();
        const recording = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        if (recording.size > 0) {
          setAudioUrl(URL.createObjectURL(recording));
          setRecordingBlob(recording);
          setVoiceState("preview");
        } else {
          setRecordingError("No audio was captured. Please try again.");
          setVoiceState("idle");
        }
      };

      setRecordingSeconds(0);
      setVoiceState("recording");
      recorder.start();
    } catch {
      setRecordingError("Microphone access was not allowed. Please enable it and try again.");
      setVoiceState("idle");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
  };

  const discardRecording = () => {
    transcriptionAbortRef.current?.abort();
    transcriptionAbortRef.current = null;
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.stop();
    }
    stopStream();
    audioRef.current?.pause();
    setAudioUrl(null);
    setRecordingBlob(null);
    setRecordingSeconds(0);
    setIsPlaying(false);
    setVoiceState("idle");
  };

  const transcribeRecording = async () => {
    if (!recordingBlob || recordingBlob.size === 0) {
      setRecordingError("No audio was captured. Please record your question again.");
      return;
    }

    setRecordingError("");
    setVoiceState("transcribing");
    const filename = recordingBlob.type.includes("wav") ? "shopy-voice.wav" : "shopy-voice.webm";
    const formData = new FormData();
    formData.append("audio", recordingBlob, filename);
    const controller = new AbortController();
    transcriptionAbortRef.current = controller;

    try {
      const response = await fetch(`${ASSISTANT_API_URL}/api/v1/transcribe`, { method: "POST", body: formData, signal: controller.signal });
      const data = await response.json() as { transcript?: string; detail?: string };
      if (!response.ok || !data.transcript) throw new Error(data.detail ?? "No speech was detected.");
      sendTextMessage(data.transcript);
      discardRecording();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setRecordingError(error instanceof Error ? error.message : "We could not transcribe that recording. Please try again.");
      setVoiceState("preview");
    } finally {
      if (transcriptionAbortRef.current === controller) transcriptionAbortRef.current = null;
    }
  };

  const togglePreviewPlayback = async () => {
    const player = audioRef.current;
    if (!player || !audioUrl) {
      setRecordingError("The recording preview is unavailable, but you can still transcribe it.");
      return;
    }

    try {
      if (player.paused) await player.play();
      else player.pause();
    } catch {
      setIsPlaying(false);
      setRecordingError("This browser cannot play the recording preview. You can still transcribe it.");
    }
  };

  const closeAssistant = () => {
    if (voiceState !== "idle") discardRecording();
    setIsOpen(false);
  };

  useEffect(() => {
    closeAssistantRef.current = closeAssistant;
  });

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;

      if (chatRef.current?.contains(target) || launcherRef.current?.contains(target)) {
        return;
      }

      closeAssistantRef.current();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeAssistantRef.current();
    };

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div data-shopy-assistant-root="">
      <button
        ref={launcherRef}
        onClick={() => isOpen ? closeAssistant() : setIsOpen(true)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        aria-label={isOpen ? "Close AI Assistant" : "Open AI Assistant"}
        style={{ right: "1.5rem", bottom: "1.5rem" }}
        aria-pressed={isOpen}
        className={`fixed z-[99999] flex h-[60px] w-[60px] items-center justify-center rounded-full border-0 bg-[linear-gradient(145deg,#7955e8,#6541d4)] text-white shadow-[0_14px_38px_rgba(45,26,117,0.42)] transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-violet-300 focus:ring-offset-2 focus:ring-offset-slate-950 ${
          isOpen ? "scale-95" : isHovered ? "-translate-y-1 scale-105" : "scale-100"
        }`}
      >
        <div className="relative flex h-full w-full items-center justify-center">
          {isOpen ? <X size={29} strokeWidth={2.1} /> : <MessageSquare size={28} strokeWidth={2.2} />}
        </div>
      </button>

      <aside
        ref={chatRef}
        role="dialog"
        aria-hidden={!isOpen}
        aria-label="AI Assistant chat"
        style={{ right: "1.5rem", bottom: "6.75rem", backgroundColor: "#ffffff" }}
        className={`${styles.chat} fixed z-[99998] flex max-w-[calc(100vw-2rem)] overflow-hidden rounded-[1.35rem] border border-slate-200 bg-white shadow-[0_28px_80px_rgba(2,6,23,0.45)] transition-all duration-300 ease-out ${
          isExpanded ? "h-[calc(100dvh-8.5rem)] w-[min(660px,calc(100vw-2rem))]" : "h-[min(760px,calc(100dvh-8.5rem))] w-[470px]"
        } ${
          isOpen ? "opacity-100 translate-y-0 pointer-events-auto" : "opacity-0 translate-y-8 pointer-events-none"
        }`}
      >
        <div className="relative flex min-h-0 w-full flex-col" style={{ backgroundColor: "#ffffff", color: "#0f172a" }}>

          <div className={styles.header}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex min-w-0 items-center gap-3">
                <div
                  aria-label="Shopy logo"
                  className={styles.brandMark}
                  style={{ backgroundImage: `url(${SHOPY_LOGO})` }}
                >
                  <span className="sr-only">Shopy</span>
                </div>
                <div className="min-w-0">
                  <p className={styles.eyebrow}>AI shopping assistant</p>
                  <h2 className={styles.title}>Shopy Assistant</h2>
                  <div className={styles.status}>
                    <span className={styles.statusDot} aria-hidden="true" />
                    Ready to help
                  </div>
                </div>
              </div>
              <div className={styles.headerActions}>
                <button onClick={() => setIsExpanded((current) => !current)} aria-label={isExpanded ? "Reduce chat size" : "Expand chat"} aria-pressed={isExpanded} className={styles.headerAction}>
                  {isExpanded ? <Minimize2 size={19} /> : <Maximize2 size={19} />}
                </button>
                <button onClick={closeAssistant} aria-label="Minimize chat" className={styles.headerAction}>
                  <X size={21} />
                </button>
              </div>
            </div>
            <p className={styles.headerPrompt}>Ask about products, orders, or today&apos;s best deals.</p>
          </div>

          <div className={styles.conversationPanel}>
            <div
              className={`${styles.messageList} space-y-5 text-sm text-slate-900`}
              style={{ backgroundColor: "#ffffff" }}
              role="log"
              aria-live="polite"
              aria-label="Chat messages"
              tabIndex={0}
            >
              {messages.map((msg) => {
                const isUser = msg.role === "user";
                return (
                  <div key={msg.id} className={`${styles.messageRow} ${isUser ? styles.userMessage : ""}`}>
                    <div className={`${styles.messageAvatar} ${isUser ? styles.userAvatar : styles.botAvatar}`} aria-label={isUser ? "Your profile" : "Shopy Assistant"}>
                      {isUser ? <UserRound size={17} strokeWidth={2.2} /> : <Bot size={18} strokeWidth={2.1} />}
                    </div>
                    <div className={styles.messageContent}>
                      <div className={`${styles.messageBubble} ${isUser ? styles.userBubble : styles.botBubble}`}>
                        <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                      </div>
                      <time
                        className={styles.messageTime}
                        dateTime={msg.timestamp?.toISOString()}
                      >
                        {msg.timestamp ? formatTime(msg.timestamp) : ""}
                      </time>
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className={styles.messageRow}>
                  <div className={`${styles.messageAvatar} ${styles.botAvatar}`} aria-label="Shopy Assistant is typing">
                    <Bot size={18} strokeWidth={2.1} />
                  </div>
                  <div className={styles.typingBubble}>
                    <div className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400 [animation-delay:120ms]" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400 [animation-delay:240ms]" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form
              onSubmit={handleSendMessage}
              className={styles.composer}
              style={{ backgroundColor: "#ffffff" }}
            >
              {voiceState === "recording" ? (
                <div className={voiceStyles.recordingBar} aria-live="polite">
                  <span className={voiceStyles.recordingDot} aria-hidden="true" />
                  <span className={voiceStyles.recordingTime}>{formatDuration(recordingSeconds)}</span>
                  <div className={voiceStyles.waveform} aria-label="Recording audio">
                    {Array.from({ length: 20 }, (_, index) => <i key={index} style={{ animationDelay: `${index * 70}ms` }} />)}
                  </div>
                  <button type="button" className={voiceStyles.stopButton} onClick={stopRecording} aria-label="Stop recording">
                    <Square size={15} fill="currentColor" />
                    <span>Stop</span>
                  </button>
                </div>
              ) : voiceState === "preview" ? (
                <div className={voiceStyles.voicePreview}>
                  <button
                    type="button"
                    className={voiceStyles.playButton}
                    onClick={() => void togglePreviewPlayback()}
                    aria-label={isPlaying ? "Pause recording" : "Play recording"}
                  >
                    {isPlaying ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}
                  </button>
                  <div className={voiceStyles.previewCopy}>
                    <strong>Voice recording</strong>
                    <span>{formatDuration(recordingSeconds)} · Ready to transcribe</span>
                  </div>
                  {audioUrl && <audio key={audioUrl} ref={audioRef} src={audioUrl} preload="metadata" onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)} onEnded={() => setIsPlaying(false)} onError={() => setRecordingError("This browser cannot play the recording preview. You can still transcribe it.")} />}
                  <button type="button" className={voiceStyles.discardButton} onClick={discardRecording} aria-label="Discard recording"><Trash2 size={18} /></button>
                  <button type="button" className={voiceStyles.sendVoiceButton} onClick={transcribeRecording} aria-label="Transcribe voice recording"><Send size={18} /></button>
                </div>
              ) : voiceState === "transcribing" ? (
                <div className={voiceStyles.transcribing} aria-live="polite">
                  <span className={voiceStyles.transcribingSpinner} aria-hidden="true" />
                  <div><strong>Transcribing your voice</strong><span>Whisper is processing this recording and sending it to Shopy Assistant.</span></div>
                </div>
              ) : (
                <>
                  <div className={styles.composerInput}>
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="Ask me anything..."
                      aria-label="Message input"
                      autoFocus
                      className="h-10 min-w-0 flex-1 !border-0 !bg-transparent !shadow-none px-3 text-base leading-6 text-slate-900 placeholder:text-slate-500 outline-none"
                      disabled={isLoading}
                    />
                    <button
                      type="button"
                      onClick={startRecording}
                      disabled={isLoading}
                      className={styles.voiceButton}
                      aria-label="Record a voice message"
                    >
                      <Mic size={19} strokeWidth={2} />
                    </button>
                    <button
                      type="submit"
                      disabled={isLoading || !input.trim()}
                      className={styles.sendButton}
                      aria-label="Send message"
                    >
                      <Send size={19} strokeWidth={2.2} />
                    </button>
                  </div>
                </>
              )}
              {recordingError && <p className={voiceStyles.recordingError} role="status">{recordingError}</p>}
            </form>
          </div>
        </div>
      </aside>

      {isOpen ? (
        <button
          type="button"
          aria-label="Close AI Assistant"
          className="fixed inset-0 z-[99990] cursor-default border-0 bg-black/20 p-0 backdrop-blur-sm"
          onClick={closeAssistant}
        />
      ) : null}
    </div>
  );
}
