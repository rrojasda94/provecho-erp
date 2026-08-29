/**
 * Una foto chica de la cámara frontal, en base64 (RN-RRHH-024, ADR-079).
 *
 * Es evidencia, no biometría: nadie la compara contra nada, solo queda
 * disponible para RRHH si algo no cuadra. Por eso el fallo es silencioso —
 * sin cámara, sin permiso o sin HTTPS, el marcaje sigue igual — y por eso
 * 320px al 60% alcanza: no hace falta reconocer una cara, alcanza con que
 * alguien la mire después.
 */

const ANCHO = 320;
const CALIDAD = 0.6;

export async function capturarFoto(): Promise<string | null> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    return null;
  }
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
  } catch {
    // Permiso denegado, sin cámara, o el navegador no la expone (http sin
    // TLS fuera de localhost): no es un error del marcaje.
    return null;
  }

  try {
    const video = document.createElement("video");
    video.srcObject = stream;
    video.muted = true;
    await video.play();
    // Un frame recién arrancada la cámara sale negro en la mayoría de
    // tablets: esperar el primer `loadeddata` es lo que garantiza que ya
    // hay imagen real antes de dibujarla al canvas.
    await new Promise<void>((resolve) => {
      if (video.readyState >= 2) return resolve();
      video.onloadeddata = () => resolve();
    });

    const alto = Math.round((ANCHO * video.videoHeight) / video.videoWidth) || ANCHO;
    const canvas = document.createElement("canvas");
    canvas.width = ANCHO;
    canvas.height = alto;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, ANCHO, alto);

    // `toDataURL` trae el encabezado `data:image/jpeg;base64,...`; el
    // servidor espera el base64 solo (`schemas.PadMarcarIn.foto`).
    const dataUrl = canvas.toDataURL("image/jpeg", CALIDAD);
    return dataUrl.split(",")[1] ?? null;
  } catch {
    return null;
  } finally {
    for (const track of stream.getTracks()) track.stop();
  }
}

/** Coordenadas del navegador, o `null` si no hay permiso, no hay GPS, o
 * tarda más de lo razonable — nunca bloquea el marcaje (RN-RRHH-024). */
export function obtenerUbicacion(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (posicion) =>
        resolve({ lat: posicion.coords.latitude, lng: posicion.coords.longitude }),
      () => resolve(null),
      { timeout: 5000, maximumAge: 60_000 },
    );
  });
}
