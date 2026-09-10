"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { InsigniaActiva } from "@/components/estado/insignia";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TablaDatos } from "@/components/tabla/tabla-datos";
import { ErrorApi } from "@/lib/cliente-api";
import {
  apiDelivery,
  ETIQUETA_VEHICULO,
  VEHICULOS,
  type Repartidor,
  type RepartidorCandidato,
  type VehiculoTipo,
} from "@/lib/delivery";
import { tienePermiso } from "@/lib/permisos";

type SucursalOpcion = { id: string; nombre: string };

type Props = {
  repartidores: Repartidor[];
  candidatos: RepartidorCandidato[];
  sucursales: SucursalOpcion[];
  permisos: string[];
};

function NuevoRepartidorDialogo({
  candidatos,
  sucursales,
  onCreado,
}: {
  candidatos: RepartidorCandidato[];
  sucursales: SucursalOpcion[];
  onCreado: (r: Repartidor) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [trabajadorId, setTrabajadorId] = useState("");
  const [sucursalId, setSucursalId] = useState(sucursales[0]?.id ?? "");
  const [vehiculo, setVehiculo] = useState<VehiculoTipo>("moto");
  const [placa, setPlaca] = useState("");
  const [telefono, setTelefono] = useState("");
  const [enviando, setEnviando] = useState(false);

  const reiniciar = () => {
    setTrabajadorId("");
    setSucursalId(sucursales[0]?.id ?? "");
    setVehiculo("moto");
    setPlaca("");
    setTelefono("");
  };

  const crear = async () => {
    if (!trabajadorId || !sucursalId) {
      toast("Elige un trabajador y una sucursal.");
      return;
    }
    setEnviando(true);
    try {
      const nuevo = await apiDelivery.crearRepartidor({
        trabajador_id: trabajadorId,
        sucursal_id: sucursalId,
        vehiculo_tipo: vehiculo,
        placa: placa.trim() || null,
        telefono: telefono.trim() || null,
      });
      toast("Repartidor dado de alta.");
      setAbierto(false);
      reiniciar();
      onCreado(nuevo);
    } catch (e) {
      toast(e instanceof ErrorApi ? e.message : "No se pudo dar de alta al repartidor.");
    } finally {
      setEnviando(false);
    }
  };

  const items = Object.fromEntries(candidatos.map((c) => [c.trabajador_id, c.nombre]));
  const sucursalItems = Object.fromEntries(sucursales.map((s) => [s.id, s.nombre]));

  return (
    <Dialog
      open={abierto}
      onOpenChange={(v) => {
        setAbierto(v);
        if (!v) reiniciar();
      }}
    >
      <DialogTrigger render={<Button disabled={candidatos.length === 0} />}>
        + Nuevo repartidor
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nuevo repartidor</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="trabajador">Trabajador</Label>
            <Select items={items} value={trabajadorId} onValueChange={(v) => setTrabajadorId(String(v))}>
              <SelectTrigger id="trabajador">
                <SelectValue placeholder="Elige un trabajador con cuenta" />
              </SelectTrigger>
              <SelectContent>
                {candidatos.map((c) => (
                  <SelectItem key={c.trabajador_id} value={c.trabajador_id}>
                    {c.nombre} · {c.cargo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {sucursales.length > 1 ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sucursal">Sucursal</Label>
              <Select
                items={sucursalItems}
                value={sucursalId}
                onValueChange={(v) => setSucursalId(String(v))}
              >
                <SelectTrigger id="sucursal">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sucursales.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="vehiculo">Vehículo</Label>
            <Select
              items={Object.fromEntries(VEHICULOS.map((v) => [v, ETIQUETA_VEHICULO[v]]))}
              value={vehiculo}
              onValueChange={(v) => setVehiculo(v as VehiculoTipo)}
            >
              <SelectTrigger id="vehiculo">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VEHICULOS.map((v) => (
                  <SelectItem key={v} value={v}>
                    {ETIQUETA_VEHICULO[v]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="placa">Placa (opcional)</Label>
            <Input id="placa" value={placa} onChange={(e) => setPlaca(e.target.value)} maxLength={10} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="telefono">Teléfono (opcional)</Label>
            <Input
              id="telefono"
              value={telefono}
              onChange={(e) => setTelefono(e.target.value)}
              maxLength={20}
            />
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setAbierto(false)}>
            Cancelar
          </Button>
          <Button type="button" onClick={crear} disabled={enviando}>
            {enviando ? "Creando…" : "Dar de alta"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditarRepartidorDialogo({
  repartidor,
  sucursales,
  onEditado,
}: {
  repartidor: Repartidor;
  sucursales: SucursalOpcion[];
  onEditado: (r: Repartidor) => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [sucursalId, setSucursalId] = useState(repartidor.sucursal_id);
  const [vehiculo, setVehiculo] = useState(repartidor.vehiculo_tipo);
  const [placa, setPlaca] = useState(repartidor.placa ?? "");
  const [telefono, setTelefono] = useState(repartidor.telefono ?? "");
  const [activo, setActivo] = useState(repartidor.activo);
  const [enviando, setEnviando] = useState(false);

  const guardar = async () => {
    setEnviando(true);
    try {
      const editado = await apiDelivery.editarRepartidor(repartidor.id, {
        sucursal_id: sucursalId,
        vehiculo_tipo: vehiculo,
        placa: placa.trim() || null,
        telefono: telefono.trim() || null,
        activo,
      });
      toast("Repartidor actualizado.");
      setAbierto(false);
      onEditado(editado);
    } catch (e) {
      toast(e instanceof ErrorApi ? e.message : "No se pudo actualizar el repartidor.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>Editar</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{repartidor.nombre ?? "Repartidor"}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {sucursales.length > 1 ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`sucursal-${repartidor.id}`}>Sucursal</Label>
              <Select
                items={Object.fromEntries(sucursales.map((s) => [s.id, s.nombre]))}
                value={sucursalId}
                onValueChange={(v) => setSucursalId(String(v))}
              >
                <SelectTrigger id={`sucursal-${repartidor.id}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sucursales.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`vehiculo-${repartidor.id}`}>Vehículo</Label>
            <Select
              items={Object.fromEntries(VEHICULOS.map((v) => [v, ETIQUETA_VEHICULO[v]]))}
              value={vehiculo}
              onValueChange={(v) => setVehiculo(v as VehiculoTipo)}
            >
              <SelectTrigger id={`vehiculo-${repartidor.id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VEHICULOS.map((v) => (
                  <SelectItem key={v} value={v}>
                    {ETIQUETA_VEHICULO[v]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`placa-${repartidor.id}`}>Placa</Label>
            <Input
              id={`placa-${repartidor.id}`}
              value={placa}
              onChange={(e) => setPlaca(e.target.value)}
              maxLength={10}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`telefono-${repartidor.id}`}>Teléfono</Label>
            <Input
              id={`telefono-${repartidor.id}`}
              value={telefono}
              onChange={(e) => setTelefono(e.target.value)}
              maxLength={20}
            />
          </div>

          <Label className="flex cursor-pointer items-center gap-2 font-normal">
            <Checkbox checked={activo} onCheckedChange={(v) => setActivo(Boolean(v))} />
            Activo
          </Label>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setAbierto(false)}>
            Cancelar
          </Button>
          <Button type="button" onClick={guardar} disabled={enviando}>
            {enviando ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function RepartidoresCliente({
  repartidores: iniciales,
  candidatos,
  sucursales,
  permisos,
}: Props) {
  const [repartidores, setRepartidores] = useState(iniciales);
  const puedeGestionar = tienePermiso(permisos, "delivery.gestionar_repartidores");

  const reemplazar = (r: Repartidor) => {
    setRepartidores((rs) => rs.map((x) => (x.id === r.id ? r : x)));
  };
  const agregar = (r: Repartidor) => {
    setRepartidores((rs) => [...rs, r]);
  };

  const columnas: ColumnDef<Repartidor>[] = useMemo(() => {
    const base: ColumnDef<Repartidor>[] = [
      { id: "nombre", header: "Repartidor", accessorFn: (r) => r.nombre ?? "(sin cuenta)" },
      {
        id: "vehiculo",
        header: "Vehículo",
        accessorFn: (r) => ETIQUETA_VEHICULO[r.vehiculo_tipo],
      },
      { id: "placa", header: "Placa", accessorFn: (r) => r.placa ?? "—" },
      { id: "telefono", header: "Teléfono", accessorFn: (r) => r.telefono ?? "—" },
      {
        accessorKey: "activo",
        header: "Estado",
        cell: ({ getValue }) => <InsigniaActiva activa={getValue<boolean>()} />,
      },
    ];
    if (!puedeGestionar) return base;
    return [
      ...base,
      {
        id: "acciones",
        header: "",
        cell: ({ row }) => (
          <EditarRepartidorDialogo
            repartidor={row.original}
            sucursales={sucursales}
            onEditado={reemplazar}
          />
        ),
      },
    ];
  }, [puedeGestionar, sucursales]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-xl text-dark">Repartidores</h1>
        {puedeGestionar ? (
          <NuevoRepartidorDialogo
            candidatos={candidatos}
            sucursales={sucursales}
            onCreado={agregar}
          />
        ) : null}
      </div>
      <TablaDatos
        columnas={columnas}
        datos={repartidores}
        placeholderBusqueda="Buscar repartidor..."
      />
    </div>
  );
}
