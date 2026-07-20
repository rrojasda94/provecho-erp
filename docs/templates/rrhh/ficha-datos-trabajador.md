<!-- Plantilla: Ficha de datos del trabajador | Módulo RRHH | Ver README.md para convención de campos -->
<!-- Uso: SOP firma-contrato-y-alta, paso 1. Se llena con los documentos originales a la vista y se envía al contador para T-Registro/PLAME. -->

# FICHA DE DATOS DEL TRABAJADOR

**Fecha:** {{ hoy }} · **Empresa:** {{ empresa.razon_social }} ·
**Sucursal:** {{ sucursal.nombre }}

## 1. Datos personales

| Campo | Dato |
|---|---|
| Nombres | {{ trabajador.nombres }} |
| Apellidos | {{ trabajador.apellidos }} |
| Tipo y N.° de documento | {{ trabajador.tipo_documento }} N.° {{ trabajador.numero_documento }} |
| Fecha de nacimiento | [[ COMPLETAR: DD/MM/AAAA ]] |
| Nacionalidad | [[ COMPLETAR ]] |
| Domicilio actual | {{ trabajador.domicilio }} |
| Teléfono / celular | [[ COMPLETAR ]] |
| Correo electrónico | [[ COMPLETAR: opcional ]] |
| Contacto de emergencia | [[ COMPLETAR: nombre, parentesco, teléfono ]] |

## 2. Datos laborales

| Campo | Dato |
|---|---|
| Puesto | {{ trabajador.cargo }} |
| Fecha de inicio | {{ trabajador.fecha_ingreso }} |
| Modalidad de contrato | [[ COMPLETAR ]] |
| Jornada | [[ COMPLETAR: completa / reducida (h) / parcial (h) ]] |
| Remuneración | S/ {{ trabajador.remuneracion_base }} |

## 3. Datos para planilla (los usa el contador)

| Campo | Dato |
|---|---|
| Sistema de pensiones | ☐ ONP · ☐ AFP: [[ COMPLETAR: cuál + CUSPP si ya está afiliado ]] · ☐ Régimen especial microempresa [[ validar opción con el contador ]] |
| Seguro de salud | ☐ SIS · ☐ ESSALUD [[ según definición de la empresa ]] |
| Cuenta para pago de haberes | [[ COMPLETAR: banco, tipo, número / "pago en efectivo con constancia mientras abre cuenta" ]] |
| ¿Primer trabajo formal? | ☐ Sí ☐ No |

## 4. Documentos verificados (marcar con los originales a la vista)

- ☐ DNI / carné de extranjería vigente (copia al file)
- ☐ Carné de sanidad vigente o en trámite — vence: [[ COMPLETAR ]]
- ☐ Antecedentes (solo puestos de caja/dinero)
- ☐ [[ COMPLETAR: otros ]]

## Declaración

Declaro que los datos consignados son verdaderos y me comprometo a comunicar
cualquier cambio de domicilio o contacto.

<br>

| EL TRABAJADOR | RECIBIDO POR |
|---|---|
| _______________________________ | _______________________________ |
| {{ trabajador.nombres }} {{ trabajador.apellidos }} | {{ emisor.nombres }} {{ emisor.apellidos }} — {{ emisor.cargo }} |

---

<sub>Enviar al contador con mínimo 2 días hábiles de anticipación al primer
día de trabajo (alta en T-Registro antes del inicio de labores). Original al
file personal. Datos personales protegidos por la Ley 29733 — uso exclusivo
para fines laborales.</sub>
