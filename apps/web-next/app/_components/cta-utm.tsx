"use client";

import { useEffect } from "react";

/**
 * Carries the campaign parameters from the ad into the offer link.
 *
 * The ad lands on the post with the UTM in the URL; the reader then clicks the
 * CTA to the store. Without this, the store sees a referrer from bestmodel.run
 * and files the lead as a plain referral: the ad that paid for the click
 * disappears from the record. With it, the store reads the same source, and
 * the lead keeps the campaign that produced it.
 *
 * The query string of the post is the only input; nothing is invented and
 * nothing is stored.
 */
const CAMPOS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_id", "utm_creative"];

export default function CtaUtm() {
  useEffect(() => {
    const entrada = new URLSearchParams(window.location.search);
    const carregados = CAMPOS.flatMap((campo) => {
      const valor = entrada.get(campo);
      return valor ? ([[campo, valor]] as [string, string][]) : [];
    });
    if (carregados.length === 0) return;
    document.querySelectorAll<HTMLAnchorElement>('.blog-prose a[href*="orbe.live"]').forEach((link) => {
      let destino: URL;
      try {
        destino = new URL(link.href);
      } catch {
        return;
      }
      let mudou = false;
      for (const [campo, valor] of carregados) {
        if (!destino.searchParams.has(campo)) {
          destino.searchParams.set(campo, valor);
          mudou = true;
        }
      }
      if (mudou) link.href = destino.toString();
    });
  }, []);
  return null;
}
