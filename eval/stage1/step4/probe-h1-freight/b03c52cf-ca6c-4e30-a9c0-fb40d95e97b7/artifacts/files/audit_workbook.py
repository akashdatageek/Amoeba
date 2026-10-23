import openpyxl

def audit():
    wb = openpyxl.load_workbook('truck_assignment_plan.xlsx')
    
    # 1. Check Sheets
    sheets = wb.sheetnames
    print(f"Sheets: {sheets}")
    
    # 2. Audit Cost Sheet Formulas
    cost_sheet = wb['Cost']
    
    # Per-truck costs are in J2:J5 (based on Step 2 memo)
    # Let's check the formulas in J2:J5
    truck_costs = []
    for row in range(2, 6):
        cell = cost_sheet[f'J{row}']
        truck_costs.append((f'J{row}', cell.value))
    
    print("\nTruck Cost Formulas (J2:J5):")
    for cell, val in truck_costs:
        print(f"{cell}: {val}")
        
    # Total cost in J6
    total_cost_cell = cost_sheet['J6']
    print(f"\nTotal Cost Formula (J6): {total_cost_cell.value}")
    
    # B8 should be =J6
    b8_cell = cost_sheet['B8']
    print(f"B8 Formula: {b8_cell.value}")

    # 3. Audit Assignment Sheet
    assign_sheet = wb['Assignment']
    # Check that B2:B11 contains the optimal assignment
    # A: L1, L2, L9; B: L5, L7, L10; C: L4, L6, L8; D: L3
    expected = {
        'L1': 'A', 'L2': 'A', 'L9': 'A',
        'L5': 'B', 'L7': 'B', 'L10': 'B',
        'L4': 'C', 'L6': 'C', 'L8': 'C',
        'L3': 'D'
    }
    
    actual = {}
    for row in range(2, 12):
        load_id = assign_sheet[f'A{row}'].value
        truck = assign_sheet[f'B{row}'].value
        actual[load_id] = truck
        
    print("\nAssignment Check:")
    match = True
    for load, truck in expected.items():
        if actual.get(load) != truck:
            print(f"Mismatch for {load}: expected {truck}, got {actual.get(load)}")
            match = False
    if match:
        print("Assignment matches optimal plan.")

    # 4. Audit Inputs Sheet
    inputs_sheet = wb['Inputs']
    # Check a few values
    # L1: 18000, 220
    print(f"\nInput L1: {inputs_sheet['B4'].value}, {inputs_sheet['C4'].value}")
    # Truck A: 45000, 1100, 350, 2.10
    print(f"Input Truck A: {inputs_sheet['B18'].value}, {inputs_sheet['C18'].value}, {inputs_sheet['D18'].value}, {inputs_sheet['E18'].value}")

audit()
