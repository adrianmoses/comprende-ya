"use client";

import { useCallback, useRef, useState } from "react";
import { VOICE_AGENT_WS_URL, SAMPLE_RATE } from "@/lib/constants";
import type { VoiceResponse } from "@/lib/voice-protocol";

export interface VoiceAgentState {
  recording: boolean;
  processing: boolean;
  lastResponse: VoiceResponse | null;
  error: string | null;
}

export function useVoiceAgent() {
  const [state, setState] = useState<VoiceAgentState>({
    recording: false,
    processing: false,
    lastResponse: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<ArrayBuffer[]>([]);

  // Playback state for sequential audio queue
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackEndTimeRef = useRef<number>(0);

  const startRecording = useCallback(async () => {
    try {
      console.log("startRecording");
      setState((s) => ({ ...s, error: null, recording: true }));

      // Set up WebSocket
      const ws = new WebSocket(VOICE_AGENT_WS_URL);
      wsRef.current = ws;

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          // Binary frame: audio sentence — queue for sequential playback
          const arrayBuffer = await event.data.arrayBuffer();
          const int16 = new Int16Array(arrayBuffer);
          const float32 = new Float32Array(int16.length);
          for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768;
          }

          // Lazily create playback context for each turn
          if (!playbackCtxRef.current) {
            playbackCtxRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
            playbackEndTimeRef.current = 0;
          }
          const ctx = playbackCtxRef.current;

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
          // Text frame: JSON metrics — turn is complete
          const data: VoiceResponse = JSON.parse(event.data);
          setState((s) => ({ ...s, lastResponse: data, processing: false }));

          // Close playback context after last audio finishes
          const ctx = playbackCtxRef.current;
          if (ctx) {
            const remaining = playbackEndTimeRef.current - ctx.currentTime;
            if (remaining > 0) {
              setTimeout(() => ctx.close(), remaining * 1000 + 100);
            } else {
              ctx.close();
            }
            playbackCtxRef.current = null;
            playbackEndTimeRef.current = 0;
          }
        }
      };

      ws.onerror = () => {
        setState((s) => ({ ...s, error: "WebSocket connection failed" }));
      };

      // Wait for WebSocket to open
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
      });

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
      playbackCtxRef.current?.close();
      playbackCtxRef.current = null;
      playbackEndTimeRef.current = 0;
      setState((s) => ({
        ...s,
        recording: false,
        error: err instanceof Error ? err.message : "Failed to start recording",
      }));
    }
  }, []);

  const stopRecording = useCallback(() => {
    console.log("stopRecording");
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

  return { ...state, startRecording, stopRecording };
}
