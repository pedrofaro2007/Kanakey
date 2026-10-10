import sys
import time
import pygame.midi

def main():
    pygame.midi.init()
    print("--- Dispositivos MIDI Encontrados ---")
    input_id = None
    for i in range(pygame.midi.get_count()):
        interf, name, is_input, is_output, opened = pygame.midi.get_device_info(i)
        name_str = name.decode('utf-8', errors='ignore')
        tipo = "Entrada" if is_input else ("Saída" if is_output else "Outro")
        print(f"[{i}] {name_str} ({tipo})")
        if is_input and ("keyboard" in name_str.lower() or "yamaha" in name_str.lower()):
            input_id = i

    if input_id is None:
        print("\nNão foi possível detectar o Yamaha automaticamente. Verifique os números acima.")
        pygame.midi.quit()
        return

    print(f"\nConectando ao dispositivo de entrada [{input_id}]...")
    midi_in = pygame.midi.Input(input_id)
    print("Pronto! Toque algumas teclas no teclado Yamaha (Ctrl+C para sair)...\n")

    try:
        while True:
            if midi_in.poll():
                events = midi_in.read(10)
                for event in events:
                    data, timestamp = event
                    status, note, velocity, data3 = data
                    msg_type = status & 0xF0
                    channel = status & 0x0F
                    if msg_type == 0x90 and velocity > 0:
                        print(f"-> Nota Pressionada: {note} | Força (Velocity): {velocity} | Canal: {channel}")
                    elif msg_type == 0x80 or (msg_type == 0x90 and velocity == 0):
                        print(f"<- Nota Solta: {note}")
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\nEncerrando teste...")
    finally:
        del midi_in
        pygame.midi.quit()

if __name__ == "__main__":
    main()
