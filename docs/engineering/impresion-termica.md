# Impresión térmica de 80 mm

Cómo sale el papel en el local: qué imprime el ERP, cómo se configura la
ticketera, y cómo se quita el diálogo del navegador.

Decisiones detrás de esto: **ADR-067**.

## Qué se imprime

| Documento | Endpoint | Quién lo dispara | Cuenta reimpresiones |
|---|---|---|---|
| Ticket del comprobante (boleta/factura) | `GET /sales/comprobantes/{id}/ticket` | PDV → Cobrados; Contabilidad → Comprobantes | No |
| Comanda de cocina | `POST /kds/ventas/{id}/comanda` | KDS; PDV → Cuentas | **Sí** (`comanda_impresa_veces`) |
| Precuenta | `GET /sales/ventas/{id}/precuenta` | PDV | No (RN-COM-019) |

Los tres salen en **48 columnas** (80 mm, fuente A de ESC/POS) y comparten el
mismo membrete: logo de la marca, razón social y RUC de la empresa, nombre y
dirección de la sucursal.

El ticket del comprobante lleva además el **QR que exige SUNAT** (RS
097-2012): RUC, tipo de documento, serie, número, IGV, total, fecha de
emisión y documento del receptor.

> El ticket **no reemplaza al PDF** de Factiliza, que sigue a un click en la
> pestaña de Contabilidad. Lo que evita es que la entrega en caja dependa de
> que un tercero conteste: si SUNAT todavía no aceptó el comprobante, el
> ticket sale igual con la franja `PENDIENTE DE ENVÍO A SUNAT`.

## Configurar el membrete de una marca

El logo y las líneas de cortesía del pie viven en `marca.skins["ticket"]`:

```json
{
  "ticket": {
    "logo": "/marcas/charlies.svg",
    "pie": [
      "Gracias por su visita",
      "Representación impresa del comprobante electrónico."
    ]
  }
}
```

- `logo` es una **ruta servida por el frontend**, no un archivo en la base.
  Los archivos viven en `frontend/public/marcas/`; cambiar el logo es
  reemplazar el archivo con el mismo nombre.
- Sin `logo`, el ticket sale con el nombre de la marca en texto, que es lo que
  importa.
- Sin `pie`, sale la línea legal por defecto.

Todo lo demás —razón social, RUC, domicilio fiscal, sucursal, dirección— sale
del padrón y **no se configura por local**: un local que escribe su propio
encabezado termina imprimiendo el RUC de la empresa equivocada.

## La impresora

1. Instalar el driver de la ticketera en el sistema operativo de la tablet o
   PC de caja (las de 80 mm suelen traer driver ESC/POS genérico).
2. Dejarla como **impresora predeterminada** del sistema. El navegador imprime
   a la predeterminada.
3. En las preferencias del driver, ancho de papel **80 mm** y corte automático
   al final del trabajo.

El tamaño de página lo fija el ERP con `@page { size: 80mm auto }`: no hay que
elegir un tamaño en el diálogo.

## Imprimir sin diálogo

El ERP llama a `window.print()`. Que eso abra o no un diálogo lo decide el
navegador, no la aplicación.

**Chrome / Edge en modo kiosco de caja** — lanzar con `--kiosk-printing`:

```bash
chrome --kiosk --kiosk-printing --app=https://erp.majambo.com.pe/pdv
```

Con esa bandera `window.print()` manda el trabajo directo a la impresora
predeterminada, sin ventana y sin confirmar. Es la configuración recomendada
para la tablet de caja y para la pantalla de cocina.

En Windows, crear un acceso directo con esos argumentos y ponerlo en el inicio
de sesión de la cuenta del local.

> `--kiosk-printing` imprime **todo** lo que la página mande a imprimir, sin
> preguntar. Úsalo solo en el equipo de caja, no en la máquina de
> administración.

Sin la bandera todo funciona igual, con el diálogo del navegador de por medio:
nadie se queda sin poder imprimir por no haberla configurado.

## Qué falta

Un **agente ESC/POS local** (o impresión directa por red al puerto 9100) sacaría
el navegador del camino: corte automático, cajón portamonedas y campana de
cocina, que el `window.print()` no puede accionar. No está hecho —ver Deuda
técnica en `docs/roadmap/deuda/modulo-sales.md`— y el trabajo de ADR-067 lo
habilita: la comanda y la precuenta ya son texto de 48 columnas, que es
exactamente lo que un ESC/POS consume.

También falta la **representación impresa de la nota de crédito**: hoy se
entrega en PDF.
