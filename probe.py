#!/opt/helios/bin/python
"""Helios: full real-time Wanderer 30A telemetry."""
from pymodbus.client import ModbusTcpClient
from pymodbus import FramerType

HOST, PORT, DEV = "10.200.200.201", 4660, 255

def main():
    c = ModbusTcpClient(host=HOST, port=PORT, framer=FramerType.RTU, timeout=3)
    c.connect()

    # Real-time: 0x0100–0x0109
    r = c.read_holding_registers(address=0x0100, count=10, device_id=DEV)
    soc, batt_v, charge_i, temp_w, load_v, load_i, load_p, pv_v, pv_i, pv_p = r.registers
    ctrl_t = temp_w >> 8;  ctrl_t -= 256 if ctrl_t >= 128 else 0
    batt_t = temp_w & 0xFF; batt_t -= 256 if batt_t >= 128 else 0

    print("=== Wanderer 30A ===")
    print(f"Battery:   {soc}% SOC, {batt_v/10:.1f} V, charge {charge_i/100:.2f} A, batt temp {batt_t}°C")
    print(f"PV:        {pv_v/10:.1f} V, {pv_i/100:.2f} A, {pv_p} W")
    print(f"Load:      {load_v/10:.1f} V, {load_i/100:.2f} A, {load_p} W")
    print(f"Ctrl temp: {ctrl_t}°C")

    # Today: 0x010B–0x0114
    r = c.read_holding_registers(address=0x010B, count=10, device_id=DEV)
    vmin, vmax, imc, imd, pmc, pmd, ahc, ahd, whg, whu = r.registers
    print(f"\n=== Today ===")
    print(f"Batt V range: {vmin/10:.1f}–{vmax/10:.1f}")
    print(f"Generated:    {whg} Wh ({ahc} Ah, peak {pmc} W)")
    print(f"Consumed:     {whu} Wh ({ahd} Ah, peak {pmd} W)")

    # State: 0x0120
    r = c.read_holding_registers(address=0x0120, count=1, device_id=DEV)
    sw = r.registers[0]
    states = {0:"Deactivated",1:"Activated",2:"MPPT",3:"Equalizing",4:"Boost",5:"Floating",6:"Current limit"}
    print(f"\n=== State ===")
    print(f"Charging: {states.get(sw & 0xFF, f'unknown({sw & 0xFF})')}, load {'ON' if sw & 0x8000 else 'OFF'}")

    c.close()

if __name__ == "__main__":
    main()
