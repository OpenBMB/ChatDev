def handle_advertising_regulation():
    # Guidelines for typical advertising regulation
    advert_rules = {
        'encourage': 'illegal activities',
        'cause_unnecessary': ['fear', 'offense'],
        'cause': 'harm' 
    }

    # Printing out the general context
    print("This function demonstrates typical advertising regulation guidelines.\n")

    # Printing out the full dictionary
    print("Advertising regulation guidelines:")
    print(advert_rules)

    # Printing out the rules with clear explanations
    print("\nTypical advertising regulatory bodies suggest, for example, that adverts must not:")
    print("- Encourage:", advert_rules['encourage'])
    print("- Cause unnecessary:", ', '.join(advert_rules['cause_unnecessary']))
    print("- Must not cause:", advert_rules['cause'])

# Run the function
handle_advertising_regulation()