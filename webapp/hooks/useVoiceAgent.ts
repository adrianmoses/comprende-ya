"use client";

import { useCallback, useRef, useState } from "react";
import { VOICE_AGENT_WS_URL, SAMPLE_RATE } from "@/lib/constants";
import type { ServerMessage, VoiceResponse } from "@/lib/voice-protocol";

export interface VoiceAgentState {
  recording: boolean;
  processing: boolean;
  lastResponse: VoiceResponse | null;
  error: string | null;
  wsConnected: boolean;
}

interface UseVoiceAgentOptions {
  onServerMessage?: (msg: ServerMessage) => void;
}

export function useVoiceAgent(options: UseVoiceAgentOptions = {}) {
  const [state, setState] = useState<VoiceAgentState>({
    recording: false,
    processing: false,
    lastResponse: null,
    error: null,
    wsConnected: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<ArrayBuffer[]>([]);
  const onServerMessageRef = useRef(options.onServerMessage);
  onServerMessageRef.current = options.onServerMessage;

  // Playback state for sequential audio queue
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackEndTimeRef = useRef<number>(0);
  const playbackCleanupRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelPlayback = useCallback(() => {
    if (playbackCleanupRef.current) {
      clearTimeout(playbackCleanupRef.current);
      playbackCleanupRef.current = null;
    }
    const ctx = playbackCtxRef.current;
    if (ctx && ctx.state !== "closed") {
      ctx.close().catch(() => {});
    }
    playbackCtxRef.current = null;
    playbackEndTimeRef.current = 0;
  }, []);

  const connectWs = useCallback(() => {
    const existing = wsRef.current;
    if (
      existing?.readyState === WebSocket.OPEN ||
      existing?.readyState === WebSocket.CONNECTING
    )
      return;

    // Close any stale connection before creating a new one
    if (existing) {
      existing.onmessage = null;
      existing.onerror = null;
      existing.onclose = null;
      existing.close();
    }

    const ws = new WebSocket(VOICE_AGENT_WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setState((s) => ({ ...s, wsConnected: true, error: null }));
    };

    ws.onmessage = async (event) => {
      if (event.data instanceof Blob) {
        // Binary frame: audio sentence — queue for sequential playback
        const arrayBuffer = await event.data.arrayBuffer();
        const int16 = new Int16Array(arrayBuffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
          float32[i] = int16[i] / 32768;
        }

        // Lazily create playback context for each turn (use default HW rate)
        if (!playbackCtxRef.current) {
          playbackCtxRef.current = new AudioContext();
          playbackEndTimeRef.current = 0;
        }
        const ctx = playbackCtxRef.current;

        // Create buffer at source sample rate — browser resamples to HW rate
        const buffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
        buffer.getChannelData(0).set(float32);
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(ctx.destination);

        // Schedule after previous audio finishes
        const startTime = Math.max(ctx.currentTime, playbackEndTimeRef.current);
        source.start(startTime);
        playbackEndTimeRef.current = startTime + buffer.duration;
      } else {
        // Text frame: JSON message
        const data = JSON.parse(event.data) as ServerMessage;

        if (data.type === "metrics") {
          setState((s) => ({
            ...s,
            lastResponse: data as VoiceResponse,
            processing: false,
          }));

          // Close playback context after all queued audio finishes
          const ctx = playbackCtxRef.current;
          if (ctx) {
            const remaining = playbackEndTimeRef.current - ctx.currentTime;
            const delayMs = Math.max(remaining, 0) * 1000 + 200;
            playbackCleanupRef.current = setTimeout(() => {
              if (ctx.state !== "closed") ctx.close().catch(() => {});
              if (playbackCtxRef.current === ctx) {
                playbackCtxRef.current = null;
                playbackEndTimeRef.current = 0;
              }
            }, delayMs);
          }
        }

        // Forward all JSON messages to callback
        onServerMessageRef.current?.(data);
      }
    };

    ws.onerror = () => {
      setState((s) => ({
        ...s,
        wsConnected: false,
        error: "WebSocket connection failed",
      }));
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, wsConnected: false }));
    };
  }, []);

  const disconnectWs = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setState((s) => ({ ...s, wsConnected: false }));
  }, []);

  const startRecording = useCallback(async () => {
    try {
      // Cancel any in-flight playback from the previous turn
      cancelPlayback();

      setState((s) => ({ ...s, error: null, recording: true }));

      // Ensure WebSocket is connected (connectWs is a no-op if already OPEN/CONNECTING)
      connectWs();
      if (wsRef.current && wsRef.current.readyState !== WebSocket.OPEN) {
        await new Promise<void>((resolve, reject) => {
          const ws = wsRef.current!;
          const onOpen = () => {
            ws.removeEventListener("open", onOpen);
            resolve();
          };
          const onError = () => {
            ws.removeEventListener("error", onError);
            reject(new Error("WebSocket connection failed"));
          };
          ws.addEventListener("open", onOpen);
          ws.addEventListener("error", onError);
        });
      }

      // Set up AudioContext + Worklet
      const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioCtxRef.current = audioCtx;
      await audioCtx.audioWorklet.addModule("/pcm-processor.js");

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const source = audioCtx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(audioCtx, "pcm-processor");
      workletRef.current = worklet;

      chunksRef.current = [];
      worklet.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        chunksRef.current.push(e.data);
      };

      source.connect(worklet);
      worklet.connect(audioCtx.destination);
    } catch (err) {
      cancelPlayback();
      setState((s) => ({
        ...s,
        recording: false,
        error: err instanceof Error ? err.message : "Failed to start recording",
      }));
    }
  }, [connectWs, cancelPlayback]);

  const stopRecording = useCallback(() => {
    setState((s) => ({ ...s, recording: false, processing: true }));

    // Stop mic
    streamRef.current?.getTracks().forEach((t) => t.stop());
    workletRef.current?.disconnect();
    audioCtxRef.current?.close();

    // Merge chunks and send
    const chunks = chunksRef.current;
    if (chunks.length > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
      const totalLen = chunks.reduce((acc, c) => acc + c.byteLength, 0);
      const merged = new Uint8Array(totalLen);
      let offset = 0;
      for (const chunk of chunks) {
        merged.set(new Uint8Array(chunk), offset);
        offset += chunk.byteLength;
      }
      wsRef.current.send(merged.buffer);
    }

    chunksRef.current = [];
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
    connectWs,
    disconnectWs,
  };
}
