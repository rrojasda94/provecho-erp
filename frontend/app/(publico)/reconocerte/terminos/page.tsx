import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Términos y condiciones | Queremos RE-conocerte",
  description:
    "Condiciones de la promoción «Queremos RE-conocerte» y tratamiento de datos personales.",
};

/**
 * Términos de la campaña.
 *
 * Es una página estática a propósito: las condiciones que el cliente aceptó
 * tienen que poder leerse igual aunque la promoción ya haya terminado y la
 * API responda 409. Los porcentajes y plazos van escritos acá y en
 * `settings.sales_promocion_cupon_*` — si alguno cambia, hay que tocar los
 * dos, y eso es correcto: cambiar el trato después de que la gente lo aceptó
 * no debería ser un ajuste de una sola variable.
 */
export default function TerminosPage() {
  return (
    <main className="publico-main publico-legal">
      <p className="publico-volver">
        <Link href="/reconocerte">← Volver</Link>
      </p>
      <h1>Términos y condiciones</h1>
      <p className="publico-legal-intro">
        Promoción <strong>«Queremos RE-conocerte»</strong> de Charlie&apos;s Pizzas,
        marca de Grupo Majambo, operada por{" "}
        <strong>Inversiones Turísticas y Alimentarias Majambo EIRL</strong>.
      </p>

      <h2>1. En qué consiste</h2>
      <p>
        Quien complete el formulario de registro recibe un cupón de{" "}
        <strong>10 % de descuento</strong> aplicable a una compra en los locales de
        la marca. El cupón se entrega en el momento y su código es el número de DNI
        registrado.
      </p>

      <h2>2. Un solo uso por cliente</h2>
      <p>
        Cada persona obtiene <strong>un único cupón</strong>. Al aplicarse en una
        compra queda desactivado de forma permanente y no vuelve a emitirse. Quien
        ya estuviera registrado —por DNI o por teléfono— obtiene igualmente su
        cupón, siempre que no lo haya usado antes.
      </p>

      <h2>3. Vigencia</h2>
      <p>
        Cada cupón vale <strong>un mes</strong> desde el día en que se emite. Pasado
        ese plazo caduca aunque no se haya usado.
      </p>
      <p>
        La campaña está vigente hasta el <strong>31 de diciembre de 2026</strong>. La
        empresa se reserva el derecho de <strong>terminarla en cualquier momento</strong>,
        sin expresión de causa. Terminarla deja de emitir cupones nuevos y{" "}
        <strong>no afecta a los ya entregados</strong>, que siguen valiendo hasta su
        propia fecha de vencimiento.
      </p>

      <h2>4. Condiciones de uso del cupón</h2>
      <ul>
        <li>Es personal e intransferible: se aplica al cliente que lo registró.</li>
        <li>Se presenta en caja antes de cerrar la cuenta.</li>
        <li>El descuento se calcula sobre el total de la orden.</li>
        <li>No es acumulable con otros descuentos sobre la misma cuenta.</li>
        <li>No se canjea por dinero ni por otros productos.</li>
      </ul>

      <h2>5. Tratamiento de datos personales</h2>
      <p>
        Los datos que dejas —nombre, DNI, fecha de nacimiento, dirección y
        teléfono— se registran para entregarte el cupón y para{" "}
        <strong>fines comerciales</strong> de Inversiones Turísticas y Alimentarias
        Majambo EIRL y de Grupo Majambo: promociones, novedades y saludos de
        cumpleaños.
      </p>
      <p>
        <strong>No vendemos ni compartimos tus datos con terceros.</strong>
      </p>
      <p>
        El tratamiento se rige por la Ley N.º 29733, Ley de Protección de Datos
        Personales, y su reglamento.
      </p>

      <h2>6. Cómo pedir que borremos tus datos</h2>
      <p>
        Escribe a <a href="mailto:hola@majambo.com.pe">hola@majambo.com.pe</a> con el
        asunto <strong>«BORRAR DATOS»</strong> e indica en el cuerpo del correo tu{" "}
        <strong>número de DNI</strong> y tu <strong>teléfono</strong>.
      </p>
      <p>
        Al procesar la solicitud tus datos personales quedan anonimizados de forma
        irreversible. Los comprobantes de compra ya emitidos se conservan sin tus
        datos identificatorios, porque la normativa tributaria obliga a guardarlos.
      </p>

      <h2>7. Aceptación</h2>
      <p>
        Completar el formulario y marcar la casilla de aceptación implica conocer y
        aceptar estos términos.
      </p>
    </main>
  );
}
