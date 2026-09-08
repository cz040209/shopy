"use client";

import Image, { type ImageProps } from "next/image";
import { useState, type ReactNode } from "react";

type ProductImageProps = Omit<ImageProps, "src" | "alt" | "onError"> & {
  src?: string;
  alt: string;
  fallback: ReactNode;
  onError?: ImageProps["onError"];
};

export default function ProductImage({
  src,
  alt,
  fallback,
  onError,
  ...imageProps
}: ProductImageProps) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const isRemoteSource = /^https?:\/\//i.test(src ?? "");

  if (!src || failedSource === src) {
    return <>{fallback}</>;
  }

  return (
    <Image
      {...imageProps}
      src={src}
      alt={alt}
      // Remote catalog media can expire. Let the browser report that failure
      // directly so the existing fallback renders without the Next optimizer
      // turning every missing source into a server-side error.
      unoptimized={imageProps.unoptimized ?? isRemoteSource}
      onError={(event) => {
        setFailedSource(src);
        onError?.(event);
      }}
    />
  );
}
