# Provecho ERP — demo para probar

Esto es el ERP completo corriendo en tu propia computadora. No usa internet,
no manda nada a ningún lado y no toca ningún sistema real: los datos son
inventados y viven solo en tu PC.

## Qué necesitas antes

**Docker Desktop** instalado y abierto: <https://docs.docker.com/desktop/>
Es gratis. Después de instalarlo, ábrelo una vez y espera a que el ícono de
la ballena deje de moverse.

## Cómo se enciende

1. Descomprime el ZIP completo en una carpeta (por ejemplo, el Escritorio).
2. Doble clic en **`INICIAR.bat`**.
3. La primera vez tarda varios minutos: está instalando todo. No cierres la
   ventana negra.
4. Cuando termina, se abre el navegador solo.

| | |
|---|---|
| Dirección | <http://localhost:3000> |
| Usuario | `admin` |
| PIN | `123456` |

## Desde el celular o la tablet

Tienen que estar en la **misma red WiFi** que la PC. En la PC, abre el menú
Inicio, escribe `cmd`, y en la ventana negra escribe `ipconfig`. Busca la
"Dirección IPv4" (algo como `192.168.1.20`). En el celular abre:

```
http://192.168.1.20:3000
```

(con el número que te salió a ti).

## Qué se puede probar

- **Punto de venta** — abrir caja, tomar un pedido, agregar extras o quitar
  ingredientes ("sin cebolla"), cobrar por varios medios de pago.
- **Carta de pizzas** — tamaños, sabores y precios armados con el lienzo de
  nodos.
- **Cocina (KDS)** — los pedidos aparecen en la pantalla de cocina.
- **Inventario** — el stock baja solo al vender, según la receta.
- **Compras** — proveedores, orden de compra, recepción de mercadería.
- **Gerencia** — dashboard del día y aprobación de parámetros propuestos.

Rompe lo que quieras. Para eso está.

## Los tres archivos

| Archivo | Qué hace |
|---------|----------|
| `INICIAR.bat` | Enciende la demo y abre el navegador |
| `APAGAR.bat` | La apaga. **Conserva** lo que cargaste |
| `REINICIAR-DEMO.bat` | **Borra todo** y deja la demo como recién instalada |

Apagar la PC no rompe nada: la próxima vez, doble clic en `INICIAR.bat` otra
vez.

## Si algo falla

- **"Docker Desktop no esta corriendo"** — ábrelo y espera a que la ballena
  deje de moverse.
- **La página no abre** — espera dos minutos más y refresca. La primera vez
  el sistema tarda en arrancar.
- **Dice que el puerto 3000 está ocupado** — abre `cmd` en la carpeta de la
  demo y escribe:

  ```
  set PUERTO_WEB=3001
  INICIAR.bat
  ```

  Luego entra a <http://localhost:3001>.
- **Cualquier otra cosa** — mándale a Renato una foto de la pantalla, qué
  estabas haciendo, y el contenido de `VERSION.txt` (dice exactamente qué
  versión te tocó).

## Lo que esta demo NO hace

- No emite comprobantes ante SUNAT: las ventas se registran, y el comprobante
  queda "pendiente".
- No manda WhatsApp ni correos.
- Todos entran con el mismo usuario `admin`, así que no hay permisos por
  puesto ni se distingue quién hizo qué.
- Tu copia es tuya: lo que cargues no lo ve nadie más, ni llega a Renato.
  Lo que encuentres, cuéntaselo.
