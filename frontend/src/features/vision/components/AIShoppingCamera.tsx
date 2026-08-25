"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, Check, ImagePlus, RotateCcw, Sparkles, SwitchCamera, X } from "lucide-react";
import styles from "./AIShoppingCamera.module.css";
import { API_URL } from "@/lib/api";

export type VisionMode = "shop_room" | "complete_look" | "shop_object";

type VisionProductAttachment = {
  product_id: string;
  product_slug?: string | null;
  name: string;
  price: string | number;
  currency: string;
  image_url: string;
  image_alt_text?: string | null;
};

type Props = {
  /** Omit this to let the shopper choose what they want to shop from the photo. */
  mode?: VisionMode;
  compact?: boolean;
  disabled?: boolean;
  maxFileSizeMb?: number;
  maxDimension?: number;
  quality?: number;
  onAnalysisComplete?: (analysis: string, attachments: VisionProductAttachment[]) => void;
};


const modeContent: Record<VisionMode, { label: string; title: string; helper: string }> = {
  shop_room: { label: "Shop a room", title: "Show us your space", helper: "Capture the room for furniture, colour, layout, and style recommendations." },
  complete_look: { label: "Complete a look", title: "Show your outfit", helper: "Capture clothing or accessories for personalised matching suggestions." },
  shop_object: { label: "Shop an object", title: "Find something similar", helper: "Capture an object to find complementary or similar products." },
};

const processingSteps = ["Detecting objects", "Understanding style", "Analyzing the space", "Searching matching products"];

export default function AIShoppingCamera({ mode, compact = false, disabled = false, maxFileSizeMb = 10, maxDimension = 1600, quality = 0.85, onAnalysisComplete }: Props) {
  const [stage, setStage] = useState<"mode_select" | "camera" | "preview" | "processing" | "result" | null>(null);
  const [selectedMode, setSelectedMode] = useState<VisionMode | null>(mode ?? null);
  const [useFrontCamera, setUseFrontCamera] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [error, setError] = useState("");
  const [processingIndex, setProcessingIndex] = useState(0);
  const [analysis, setAnalysis] = useState("");
  const [isCameraReady, setIsCameraReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeMode = selectedMode ?? mode ?? "shop_object";

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const releasePreview = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setPhoto(null);
  };

  const close = () => {
    stopCamera();
    releasePreview();
    setError("");
    setAnalysis("");
    setSelectedMode(mode ?? null);
    setStage(null);
  };

  const startCamera = async (front = useFrontCamera) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Your browser does not support camera access. Choose a photo from your gallery instead.");
      setStage("camera");
      return;
    }
    try {
      setError("");
      setIsCameraReady(false);
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: front ? "user" : "environment" } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsCameraReady(true);
      setStage("camera");
    } catch (cameraError) {
      const name = cameraError instanceof DOMException ? cameraError.name : "";
      setError(name === "NotAllowedError" ? "Camera permission was denied. Enable it in your browser settings or choose a gallery photo." : "We couldn’t start the camera. You can still choose a photo from your gallery.");
      setIsCameraReady(false);
      setStage("camera");
    }
  };

  const open = () => {
    if (mode) {
      setSelectedMode(mode);
      void startCamera(false);
      return;
    }
    setStage("mode_select");
  };

  const selectMode = (nextMode: VisionMode) => {
    setSelectedMode(nextMode);
    void startCamera(false);
  };

  const prepareImage = async (source: Blob) => {
    if (!source.type.startsWith("image/")) throw new Error("Please choose an image file.");
    if (source.size > maxFileSizeMb * 1024 * 1024) throw new Error(`Choose an image smaller than ${maxFileSizeMb} MB.`);

    const sourceUrl = URL.createObjectURL(source);
    try {
      const image = new window.Image();
      image.src = sourceUrl;
      await image.decode();
      const scale = Math.min(1, maxDimension / Math.max(image.naturalWidth, image.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Unable to prepare this image.");
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const compressed = await new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Unable to compress this image.")), "image/jpeg", quality));
      releasePreview();
      setPhoto(compressed);
      setPreviewUrl(URL.createObjectURL(compressed));
      stopCamera();
      setStage("preview");
    } finally {
      URL.revokeObjectURL(sourceUrl);
    }
  };

  const capture = async () => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) {
        setError("We couldn’t capture that photo. Please try again.");
        return;
      }
      void prepareImage(blob).catch((captureError: Error) => setError(captureError.message));
    }, "image/jpeg", quality);
  };

  const chooseFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      setError("");
      await prepareImage(file);
    } catch (fileError) {
      setError(fileError instanceof Error ? fileError.message : "We couldn’t use that image.");
    }
  };

  const retake = () => {
    releasePreview();
    setStage("camera");
    void startCamera(useFrontCamera);
  };

  const submitPhoto = async () => {
    if (!photo) return;
    setStage("processing");
    setProcessingIndex(0);
    const progressTimer = window.setInterval(() => setProcessingIndex((current) => Math.min(current + 1, processingSteps.length - 1)), 750);
    try {
      const data = new FormData();
      data.append("image", photo, "shopy-vision.jpg");
      data.append("mode", activeMode);
      const response = await fetch(`${API_URL}/api/v1/shopping/missions/vision`, { method: "POST", credentials: "include", body: data });
      const result = await response.json() as { analysis?: string; detail?: string; attachments?: VisionProductAttachment[] };
      if (!response.ok || !result.analysis) throw new Error(result.detail ?? "AI analysis could not be completed.");
      setAnalysis(result.analysis);
      onAnalysisComplete?.(result.analysis, result.attachments ?? []);
      setStage("result");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "AI analysis could not be completed.");
      setStage("preview");
    } finally {
      window.clearInterval(progressTimer);
    }
  };

  useEffect(() => () => {
    stopCamera();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  // stop tracks and release image memory if the feature unmounts
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <button type="button" disabled={disabled} className={`${styles.trigger} ${compact ? styles.compactTrigger : ""}`} onClick={open} aria-label={mode ? modeContent[mode].label : "Shop with a photo"}>
        <Camera size={compact ? 19 : 17} /><span>{mode ? modeContent[mode].label : "Shop with a photo"}</span>
      </button>
      <input ref={fileInputRef} className={styles.fileInput} type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseFile} />

      {stage && (
        <section className={styles.overlay} data-shopy-camera-overlay="" role="dialog" aria-modal="true" aria-label={modeContent[activeMode].label}>
          <div className={styles.cameraShell}>
            <header className={styles.header}>
              <div><span>{modeContent[activeMode].label}</span><strong>{stage === "processing" ? "AI analysis" : modeContent[activeMode].title}</strong></div>
              <button type="button" className={styles.iconButton} onClick={close} aria-label="Close camera"><X size={22} /></button>
            </header>

            {stage === "mode_select" && <div className={styles.modeSelectStage}>
              <div className={styles.processingOrb}><Camera size={30} /></div>
              <h2>What would you like to shop?</h2>
              <p>Choose a photo type, then take a picture with your camera or select one from your gallery.</p>
              <div className={styles.modeChoices}>
                {(Object.keys(modeContent) as VisionMode[]).map((choice) => (
                  <button key={choice} type="button" onClick={() => selectMode(choice)}>
                    <strong>{modeContent[choice].label}</strong><span>{modeContent[choice].helper}</span>
                  </button>
                ))}
              </div>
            </div>}
            {stage === "camera" && <div className={styles.cameraStage}>
              <video ref={videoRef} className={styles.video} playsInline muted autoPlay />
              {!isCameraReady && <div className={styles.cameraEmpty}><Camera size={34} /><p>Camera preview will appear here.</p></div>}
              <div className={styles.cameraGradient} />
              <div className={styles.modeHelper}>{modeContent[activeMode].helper}</div>
              <div style={{ position: "absolute", right: 20, bottom: 132, left: 20, color: "#d7dded", fontSize: 11, lineHeight: 1.4, textAlign: "center", textShadow: "0 1px 10px #000" }}>Your photo stays on this device until you choose <strong style={{ color: "#fff" }}>Use photo</strong>.</div>
              {error && <p className={styles.error}>{error}</p>}
              <div className={styles.cameraControls}>
                <button type="button" className={styles.galleryButton} onClick={() => fileInputRef.current?.click()}><ImagePlus size={19} /><span>Gallery</span></button>
                <button type="button" className={styles.shutter} onClick={() => void capture()} aria-label="Capture photo"><span /></button>
                <button type="button" className={styles.galleryButton} onClick={() => { const next = !useFrontCamera; setUseFrontCamera(next); void startCamera(next); }} aria-label="Switch camera"><SwitchCamera size={21} /><span>Flip</span></button>
              </div>
            </div>}

            {stage === "preview" && previewUrl && <div className={styles.previewStage}>
              {/* Blob URLs are created locally after explicit capture and are never stored automatically. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previewUrl} alt="Your captured photo" className={styles.previewImage} />
              <div className={styles.previewScrim} />
              <div style={{ position: "absolute", right: 20, bottom: 98, left: 20, color: "#d7dded", fontSize: 11, lineHeight: 1.4, textAlign: "center", textShadow: "0 1px 10px #000" }}>Review your photo before it is sent for AI analysis.</div>
              {error && <p className={styles.error}>{error}</p>}
              <div className={styles.previewActions}>
                <button type="button" className={styles.secondaryAction} onClick={retake}><RotateCcw size={18} />Retake</button>
                <button type="button" className={styles.primaryAction} onClick={() => void submitPhoto()}><Sparkles size={18} />Use photo</button>
              </div>
            </div>}

            {stage === "processing" && <div className={styles.processingStage}>
              <div className={styles.processingOrb}><Sparkles size={30} /></div>
              <h2>Creating your shopping mission</h2>
              <p>Shopy AI is turning your photo into relevant product ideas.</p>
              <ol className={styles.steps}>{processingSteps.map((step, index) => <li key={step} className={index <= processingIndex ? styles.stepActive : ""}><span>{index < processingIndex ? <Check size={14} /> : index + 1}</span>{step}</li>)}</ol>
            </div>}

            {stage === "result" && <div className={styles.resultStage}>
              <div className={styles.processingOrb}><Sparkles size={30} /></div>
              <h2>Your AI shopping brief</h2>
              <p>{analysis}</p>
              <button type="button" className={styles.primaryAction} onClick={close}>Done</button>
            </div>}
          </div>
        </section>
      )}
    </>
  );
}
