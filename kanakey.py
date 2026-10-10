import os
import sys
import json
import time
import argparse

# Configura codificação UTF-8 no terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame.midi
from pynput.keyboard import Controller, Key

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def note_number_to_name(note_num: int) -> str:
    name = NOTE_NAMES[note_num % 12]
    octave = (note_num // 12) - 1
    return f"{name}{octave}"

SPECIAL_KEYS = {
    "space": Key.space,
    "enter": Key.enter,
    "return": Key.enter,
    "backspace": Key.backspace,
    "tab": Key.tab,
    "esc": Key.esc,
    "escape": Key.esc,
    "shift": Key.shift,
    "ctrl": Key.ctrl,
    "control": Key.ctrl,
    "alt": Key.alt,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "caps_lock": Key.caps_lock,
    "delete": Key.delete,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
}

SHIFT_SYMBOL_MAP = {
    "!": "1",
    "@": "2",
    "$": "4",
    "%": "5",
    "^": "6",
    "*": "8",
    "(": "9",
}

def resolve_target_key(key_str: str):
    key_clean = key_str.strip()
    key_lower = key_clean.lower()

    if key_lower in SPECIAL_KEYS:
        return SPECIAL_KEYS[key_lower], False, key_clean

    if key_clean in SHIFT_SYMBOL_MAP:
        base_char = SHIFT_SYMBOL_MAP[key_clean]
        return base_char, True, f"{key_clean} (Shift+{base_char})"

    if len(key_clean) == 1 and key_clean.isupper():
        base_char = key_clean.lower()
        return base_char, True, f"{key_clean} (Shift+{base_char})"

    return key_clean, False, key_clean


class KeyboardManager:
    def __init__(self):
        self.controller = Controller()
        self.shift_held = False
        self.active_shifted_notes = set()
        self.active_notes = {}  # note -> (base_key, is_shifted, display_name)

    def press_note(self, note: int, base_key, is_shifted: bool, display_name: str):
        if is_shifted:
            if not self.shift_held:
                self.controller.press(Key.shift)
                self.shift_held = True
            self.active_shifted_notes.add(note)
            self.controller.press(base_key)
        else:
            if self.shift_held:
                self.controller.release(Key.shift)
                self.controller.press(base_key)
                if self.active_shifted_notes:
                    self.controller.press(Key.shift)
                else:
                    self.shift_held = False
            else:
                self.controller.press(base_key)

        self.active_notes[note] = (base_key, is_shifted, display_name)

    def release_note(self, note: int):
        if note not in self.active_notes:
            return None
        base_key, is_shifted, display_name = self.active_notes.pop(note)
        try:
            self.controller.release(base_key)
        except Exception:
            pass

        if is_shifted:
            self.active_shifted_notes.discard(note)
            if not self.active_shifted_notes and self.shift_held:
                self.controller.release(Key.shift)
                self.shift_held = False

        return display_name

    def release_all(self):
        for note, (base_key, _, _) in list(self.active_notes.items()):
            try:
                self.controller.release(base_key)
            except Exception:
                pass
        self.active_notes.clear()
        self.active_shifted_notes.clear()
        if self.shift_held:
            try:
                self.controller.release(Key.shift)
            except Exception:
                pass
            self.shift_held = False


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"device_name_pattern": "keyboard", "active_preset": "virtual_piano", "presets": {}}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Erro ao carregar config.json: {e}")
        return {}

def find_midi_input_device(pattern: str = "keyboard"):
    count = pygame.midi.get_count()
    matching_devices = []
    first_input = None

    for i in range(count):
        _, name_bytes, is_input, _, _ = pygame.midi.get_device_info(i)
        name = name_bytes.decode("utf-8", errors="ignore")
        if is_input:
            if first_input is None:
                first_input = (i, name)
            if pattern.lower() in name.lower() or "yamaha" in name.lower():
                matching_devices.append((i, name))

    if matching_devices:
        return matching_devices[0]
    return first_input

def run_monitor(midi_in):
    os.system("cls" if os.name == "nt" else "clear")
    print("=========================")
    print("MODO MONITOR")
    print("Toque no piano para ver as notas.")
    print("Pressione Ctrl+C para voltar ao menu.")
    print("=========================\n")
    try:
        while True:
            if midi_in.poll():
                events = midi_in.read(10)
                for event in events:
                    data, _ = event
                    status, note, velocity, _ = data
                    msg_type = status & 0xF0
                    if msg_type == 0x90 and velocity > 0:
                        name = note_number_to_name(note)
                        print(f"Nota: {note:<3} ({name:<4}) | Velocity: {velocity}")
                    elif msg_type == 0x80 or (msg_type == 0x90 and velocity == 0):
                        name = note_number_to_name(note)
                        print(f"Soltou: {note:<3} ({name:<4})")
            time.sleep(0.002)
    except KeyboardInterrupt:
        print("\n\nVoltando ao menu...")
        time.sleep(1)

def run_translator(midi_in, config, preset_name):
    os.system("cls" if os.name == "nt" else "clear")
    kb_mgr = KeyboardManager()

    preset = config.get("presets", {}).get(preset_name, {})
    raw_map = preset.get("mapa", {})

    note_map = {}
    for note_str, key_str in raw_map.items():
        try:
            n = int(note_str)
            base_key, is_shifted, display_name = resolve_target_key(key_str)
            note_map[n] = (base_key, is_shifted, display_name)
        except ValueError:
            pass

    print("=========================")
    print("TRADUÇÃO ATIVA (MIDI -> caractere)")
    print(f"Teclas mapeadas: {len(note_map)}")
    print("Pressione Ctrl+C para voltar ao menu.")
    print("=========================\n")

    try:
        while True:
            if midi_in.poll():
                events = midi_in.read(15)
                for event in events:
                    data, _ = event
                    status, note, velocity, _ = data
                    msg_type = status & 0xF0

                    # Nota pressionada
                    if msg_type == 0x90 and velocity > 0:
                        if note in note_map:
                            base_key, is_shifted, display_name = note_map[note]
                            try:
                                kb_mgr.press_note(note, base_key, is_shifted, display_name)
                                print(f"[ON]  {note:<3} ({note_number_to_name(note):<4}) -> '{display_name}'")
                            except Exception as ex:
                                print(f"[!] Erro ao pressionar {display_name}: {ex}")
                        else:
                            print(f"[--]  {note:<3} ({note_number_to_name(note):<4}) (não mapeada)")

                    # Nota solta
                    elif msg_type == 0x80 or (msg_type == 0x90 and velocity == 0):
                        disp = kb_mgr.release_note(note)
                        if disp:
                            print(f"[OFF] {note:<3} ({note_number_to_name(note):<4}) -> '{disp}'")

            time.sleep(0.001)
    except KeyboardInterrupt:
        print("\n\nVoltando ao menu...")
        time.sleep(1)
    finally:
        kb_mgr.release_all()

def main():
    parser = argparse.ArgumentParser(description="Kanakey")
    parser.add_argument("--preset", type=str, help="Preset")
    parser.add_argument("--monitor", action="store_true", help="Monitor")
    args = parser.parse_args()

    pygame.midi.init()
    try:
        config = load_config()
        pattern = config.get("device_name_pattern", "keyboard")

        device_info = find_midi_input_device(pattern)
        if not device_info:
            print("=========================")
            print("[X] Nenhum dispositivo MIDI conectado.")
            print("Verifique se o cabo USB do Yamaha está plugado.")
            print("=========================")
            input("\nPressione Enter para sair...")
            return

        device_id, device_name = device_info
        midi_in = pygame.midi.Input(device_id)

        preset_name = args.preset or config.get("active_preset", "virtual_piano")

        # Se passou flag direta por linha de comando
        if args.monitor:
            run_monitor(midi_in)
            return

        # Loop do Menu Principal
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print("[1] Iniciar tradução (MIDI -> caractere)")
            print("[2] Monitor")
            print("[3] Sair")
            opt = input("Escolha uma opção [1-3]: ").strip()

            if opt == "1":
                run_translator(midi_in, config, preset_name)
            elif opt == "2":
                run_monitor(midi_in)
            elif opt == "3":
                break

    finally:
        try:
            del midi_in
        except Exception:
            pass
        pygame.midi.quit()

if __name__ == "__main__":
    main()
