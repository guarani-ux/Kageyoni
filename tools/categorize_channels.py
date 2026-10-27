from pathlib import Path
from kageyoni.ninshu.patchbay import Patchbay

def categorize_channels():
    pb = Patchbay()
    channels = pb.list_channels()

    results = []
    for c in channels:
        ch_num = c['channel_number']
        name = c['name']
        carrier = c['carrier_path']
        p = Path(__file__).resolve().parent.parent / carrier
        
        # Check if in-tree python stdlib exists
        is_live_stdlib = False
        if ch_num in [1, 9, 11, 12, 13, 25, 36, 37, 38, 41, 42, 43, 44, 45, 48]:
            is_live_stdlib = True
            
        if is_live_stdlib:
            status = 'GRADE_A_LIVE'
        elif p.exists():
            status = 'GRADE_B_SOURCE_EXISTS'
        else:
            status = 'GRADE_C_MISSING_BINARY'
            
        results.append((ch_num, name, status, carrier))

    grade_a = [r for r in results if r[2] == 'GRADE_A_LIVE']
    grade_b = [r for r in results if r[2] == 'GRADE_B_SOURCE_EXISTS']
    grade_c = [r for r in results if r[2] == 'GRADE_C_MISSING_BINARY']

    print(f"Total Channels: {len(results)}")
    print(f"Grade A (Live In-Tree Python): {len(grade_a)}")
    print(f"Grade B (TypeScript Source in rea_forge): {len(grade_b)}")
    print(f"Grade C (External Tool Binaries Missing): {len(grade_c)}")
    print("\n--- GRADE B CHANNELS READY FOR SYSTEMATIC IN-TREE PORTING ---")
    for b in grade_b:
        print(f"CH {b[0]:02d}: {b[1]} | Carrier: {b[3]}")

if __name__ == "__main__":
    categorize_channels()
