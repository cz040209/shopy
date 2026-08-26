"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Camera, Check, ImagePlus, LampFloor, MonitorUp, PackageOpen, RotateCcw, ShoppingBag, SwitchCamera, X } from "lucide-react";
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
  brand?: string | null;
  category?: string | null;
};

type VisionContext = {
  detected_objects?: string[];
  category?: string[];
  colors?: string[];
  style?: string[];
  existing_items?: string[];
  possible_shopping_needs?: string[];
  visual_constraints?: string[];
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
const MAX_CAMERA_CAPTURE_WIDTH = 3840;
const MAX_CAMERA_CAPTURE_HEIGHT = 2160;
const MAX_SOURCE_FILE_MULTIPLIER = 3;

export default function AIShoppingCamera({ mode, compact = false, disabled = false, maxFileSizeMb = 10, maxDimension = 2048, quality = 0.92, onAnalysisComplete }: Props) {
  const [stage, setStage] = useState<"mode_select" | "camera" | "preview" | "processing" | "result" | null>(null);
  const [selectedMode, setSelectedMode] = useState<VisionMode | null>(mode ?? null);
  const [useFrontCamera, setUseFrontCamera] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [error, setError] = useState("");
  const [processingIndex, setProcessingIndex] = useState(0);
  const [analysis, setAnalysis] = useState("");
  const [attachments, setAttachments] = useState<VisionProductAttachment[]>([]);
  const [visionContext, setVisionContext] = useState<VisionContext>({});
  const [lookStyle, setLookStyle] = useState("Minimalist");
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
    setAttachments([]);
    setVisionContext({});
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
        video: {
          facingMode: { ideal: front ? "user" : "environment" },
          // "ideal" lets each laptop or phone select its best supported camera
          // mode without failing on hardware that cannot provide 4K.
          width: { ideal: MAX_CAMERA_CAPTURE_WIDTH },
          height: { ideal: MAX_CAMERA_CAPTURE_HEIGHT },
          aspectRatio: { ideal: 16 / 9 },
          frameRate: { ideal: 30, max: 30 },
        },
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
    if (source.size > maxFileSizeMb * MAX_SOURCE_FILE_MULTIPLIER * 1024 * 1024) {
      throw new Error(`Choose an image smaller than ${maxFileSizeMb * MAX_SOURCE_FILE_MULTIPLIER} MB.`);
    }

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
      context.imageSmoothingEnabled = true;
      context.imageSmoothingQuality = "high";
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const compressed = await new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Unable to compress this image.")), "image/jpeg", quality));
      if (compressed.size > maxFileSizeMb * 1024 * 1024) {
        throw new Error("This image is still too large after preparation. Please choose a different photo.");
      }
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

  const submitPhoto = async (styleDirection?: string) => {
    if (!photo) return;
    setStage("processing");
    setProcessingIndex(0);
    const progressTimer = window.setInterval(() => setProcessingIndex((current) => Math.min(current + 1, processingSteps.length - 1)), 750);
    try {
      const data = new FormData();
      data.append("image", photo, "shopy-vision.jpg");
      data.append("mode", activeMode);
      if (styleDirection) data.append("style", styleDirection);
      const response = await fetch(`${API_URL}/api/v1/shopping/missions/vision`, { method: "POST", credentials: "include", body: data });
      const result = await response.json() as { analysis?: string; detail?: string; attachments?: VisionProductAttachment[]; vision_context?: VisionContext };
      if (!response.ok || !result.analysis) throw new Error(result.detail ?? "AI analysis could not be completed.");
      setAnalysis(result.analysis);
      setAttachments(result.attachments ?? []);
      setVisionContext(result.vision_context ?? {});
      if (styleDirection) setLookStyle(styleDirection);
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

  const visualProducts = attachments.slice(0, 4);
  const isRoom = activeMode === "shop_room";
  const isLook = activeMode === "complete_look";
  const existingItems = visionContext.existing_items ?? [];
  const shoppingNeeds = visionContext.possible_shopping_needs ?? [];
  const detectedStyle = [...(visionContext.style ?? []), ...(visionContext.colors ?? [])].slice(0, 4);

  return (
    <>
      <button type="button" disabled={disabled} className={`${styles.trigger} ${compact ? styles.compactTrigger : ""}`} onClick={open} aria-label={mode ? modeContent[mode].label : "Shop with a photo"}>
        <Camera size={compact ? 19 : 17} /><span>{mode ? modeContent[mode].label : "Shop with a photo"}</span>
      </button>
      <input ref={fileInputRef} className={styles.fileInput} type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseFile} />

      {stage && createPortal(
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
              <img src={previewUrl} alt="Your captured photo" className={styles.previewImage} />
              <div className={styles.previewScrim} />
              <div style={{ position: "absolute", right: 20, bottom: 98, left: 20, color: "#d7dded", fontSize: 11, lineHeight: 1.4, textAlign: "center", textShadow: "0 1px 10px #000" }}>Review your photo before it is sent for AI analysis.</div>
              {error && <p className={styles.error}>{error}</p>}
              <div className={styles.previewActions}>
                <button type="button" className={styles.secondaryAction} onClick={retake}><RotateCcw size={18} />Retake</button>
                <button type="button" className={styles.primaryAction} onClick={() => void submitPhoto()}><Camera size={18} />Use photo</button>
              </div>
            </div>}

            {stage === "processing" && <div className={styles.processingStage}>
              <div className={styles.processingOrb}><Camera size={30} /></div>
              <h2>Creating your shopping mission</h2>
              <p>Shopy AI is turning your photo into relevant product ideas.</p>
              <ol className={styles.steps}>{processingSteps.map((step, index) => <li key={step} className={index <= processingIndex ? styles.stepActive : ""}><span>{index < processingIndex ? <Check size={14} /> : index + 1}</span>{step}</li>)}</ol>
            </div>}

            {stage === "result" && (isRoom || isLook) && <div className={styles.visualResultStage}>
              <div className={styles.visualScroll}>
                {isRoom && <>
                  <div className={styles.canvasIntro}><span>YOUR ROOM, REIMAGINED</span><h2>AI found {Math.max(visualProducts.length, 3)} opportunities</h2></div>
                  <div className={styles.roomCanvas}>
                    {previewUrl && <img src={previewUrl} alt="Your room" />}
                    <div className={styles.canvasShade} />
                    {existingItems.slice(0, 3).map((item, index) => <span className={`${styles.roomTag} ${[styles.bedTag, styles.chairTag, styles.spaceTag][index]}`} key={item}>{index === 0 ? "◆" : index === 1 ? "●" : "■"} Existing {item}</span>)}
                    {shoppingNeeds.length > 0 && <span className={`${styles.roomTag} ${styles.spaceTag}`}>✦ Opportunity detected</span>}
                    <span className={styles.roomTitle}>YOUR ROOM</span>
                  </div>
                  <p className={styles.analysis}>{analysis}</p>
                  <div className={styles.opportunityList}>
                    {(shoppingNeeds.length ? shoppingNeeds : visualProducts.map((product) => product.category || product.name)).slice(0, 4).map((need, index) => {
                      const product = visualProducts[index]; const Icon = [LampFloor, PackageOpen, MonitorUp, Camera][index] ?? Camera;
                      return <article className={styles.opportunity} key={need}><span className={styles.opportunityIcon}><Icon size={19} /></span><div><small>0{index + 1} — {need}</small><p>{visionContext.visual_constraints?.[index] || `A considered addition for the ${need.toLowerCase()} opportunity detected in your room.`}</p>{product && <strong>{product.name} <b>RM {Number(product.price).toLocaleString("en-MY", { minimumFractionDigits: 0 })}</b></strong>}</div></article>;
                    })}
                  </div>
                </>}
                {isLook && <>
                  <div className={styles.canvasIntro}><span>COMPLETE YOUR LOOK</span><h2>Built around what you already wear</h2></div>
                  <div className={styles.lookCanvas}>
                    <span className={styles.lookStyle}>STYLE DETECTED · {detectedStyle.length ? detectedStyle.join(" · ").toUpperCase() : "ANALYZED FROM YOUR PHOTO"}</span>
                    <div className={styles.lookTop}>{visualProducts[0] ? <><span>🧢</span><small>{visualProducts[0].name}<b>RM {Number(visualProducts[0].price).toLocaleString("en-MY", { minimumFractionDigits: 0 })}</b></small></> : "🧢"}</div>
                    <div className={styles.lookPerson}>{previewUrl && <img src={previewUrl} alt="Your outfit" />}<span>{existingItems.slice(0, 3).join(" · ") || "YOUR CURRENT LOOK"}</span></div>
                    <div className={styles.lookAccessories}>{visualProducts.slice(1, 3).map((product, index) => <div key={product.product_id}><span>{index ? "👜" : "⌚"}</span><small>{product.name}<b>RM {Number(product.price).toLocaleString("en-MY", { minimumFractionDigits: 0 })}</b></small></div>)}</div>
                  </div>
                  <div className={styles.styleChoices}>{["Streetwear", "Smart Casual", "Minimalist", "Date Night"].map((style) => <button type="button" key={style} onClick={() => void submitPhoto(style)} className={style === lookStyle ? styles.activeStyle : ""}>{style}</button>)}</div>
                  <p className={styles.analysis}>{analysis}</p>
                </>}
                <button type="button" className={styles.completeAction} onClick={close}><ShoppingBag size={17} />{isRoom ? `Complete this room${visualProducts.length ? ` · RM ${visualProducts.reduce((total, product) => total + Number(product.price), 0).toLocaleString("en-MY", { maximumFractionDigits: 0 })}` : ""}` : `Shop the ${lookStyle.toLowerCase()} edit`}</button>
              </div>
            </div>}
            {stage === "result" && !isRoom && !isLook && <div className={styles.resultStage}>
              <div className={styles.processingOrb}><Camera size={30} /></div><h2>Your AI shopping brief</h2><p>{analysis}</p><button type="button" className={styles.primaryAction} onClick={close}>Done</button>
            </div>}
          </div>
        </section>
      , document.body)}
    </>
  );
}
