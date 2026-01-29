# Finger Exercise: Find a root and pwr (1 < pwr < 6) such that root**pwr == val

# 1. Get input from the user
val = int(input("Enter an integer: "))

# 2. Initialize variables
# We start pwr at 2 because the constraint is 1 < pwr < 6
pwr = 2
found = False

# 3. Outer loop: Check each possible power (2, 3, 4, 5)
while pwr < 6:
    # 4. Inner loop: Check possible roots
    # We use the absolute value of val to set a search limit
    # We start searching from the negative of the value to handle negative inputs
    root = -abs(val)
    
    while root <= abs(val):
        # Check if current root raised to current pwr equals the input
        if root**pwr == val:
            print(f"root: {root}, pwr: {pwr}")
            found = True
        
        root += 1 # Increment the root to check the next integer
    
    pwr += 1 # Increment pwr to check the next power (e.g., move from squared to cubed)

# 5. Final check
if not found:
    print("No such pair of integers exists.")