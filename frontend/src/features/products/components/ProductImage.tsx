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

  if (!src || failedSource === src) {
    return <>{fallback}</>;
  }

  return (
    <Image
      {...imageProps}
      src={src}
      alt={alt}
      onError={(event) => {
        setFailedSource(src);
        onError?.(event);
      }}
    />
  );
}
