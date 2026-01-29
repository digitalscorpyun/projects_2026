# Finger exercise: Sum of primes > 2 and < 1000

prime_sum = 0
candidate = 3  # Start at 3 as per the hint (greater than 2)

# Outer loop iterates over the odd integers
while candidate < 1000:
    is_prime = True
    divisor = 2 
    
    # Inner loop is the primality test
    # We check if 'candidate' is divisible by any number smaller than it
    while divisor < candidate:
        if candidate % divisor == 0:
            is_prime = False
            break # Found a factor, so it's not prime. Stop the inner loop.
        divisor += 1
        
    if is_prime:
        prime_sum += candidate
        
    candidate += 2 # Move to the next odd integer

print(f"The sum of prime numbers between 2 and 1000 is: {prime_sum}")