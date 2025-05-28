import re

def cpp_to_mojo_type(cpp_type_str):
    """Maps C++ type strings to Mojo type strings."""
    cpp_type_lower = cpp_type_str.lower()
    if "long" in cpp_type_lower: # Handles 'long', 'const long' etc.
        return "Int64"
    elif "std::uint32_t" in cpp_type_lower or "uint32_t" in cpp_type_lower :
        return "UInt32"
    elif "std::int32_t" in cpp_type_lower or "int32_t" in cpp_type_lower:
        return "Int32"
    elif "int" in cpp_type_lower: # General int, could be platform dependent in C++
        return "Int32" # Defaulting to Int32 for generic 'int'
    # Add more specific mappings if needed
    else:
        print(f"Warning: Unknown C++ type '{cpp_type_str}', defaulting to 'SIMD[DType.si64, 1]'. Manual review needed for Mojo type.")
        return "SIMD[DType.si64, 1]"

def generate_mojo_init_body(cpp_code_string, 
                            data_array_prefix_cxx, # e.g., "AltPrimitivePolynomialDegree" or "dim"
                            data_array_suffix_cxx, # e.g., "" or "KuoInit"
                            data_array_base_mojo,  # e.g., "degree" or "data_dim"
                            main_pointer_array_cxx, # e.g., "AltPrimitivePolynomials" or "Kuoinitializers"
                            main_pointer_array_mojo="pointers" # Default Mojo name for the pointer array
                           ):
    """
    Generates the Mojo __init__ body from C++ constant array definitions.
    - data_array_prefix_cxx + number + data_array_suffix_cxx defines the C++ data array name.
    - data_array_base_mojo + number defines the Mojo data member name.
    """
    mojo_init_lines = []
    data_arrays_info = [] 
    
    # Regex for individual data arrays. Example: const long AltPrimitivePolynomialDegree01[] = { ... };
    # or const std::uint32_t dim1KuoInit[] = { ... };
    # The number part is now more flexible ((\d\d) for two digits, or (\d+) for one or more)
    # We'll try to match common patterns like two digits first, then one or more.
    
    # Pattern for names like "AltPrimitivePolynomialDegree01" (two digits for number)
    data_array_pattern_num_suffix_two_digits = re.compile(
        r"const\s+(?P<type>\w[\w\s\:]*(?:_t)?)\s+"  # Capture type (e.g., long, std::uint32_t, const int)
        r"(?P<cxx_name>" + re.escape(data_array_prefix_cxx) + r"(?P<num_str>\d\d)" + re.escape(data_array_suffix_cxx) + r")"
        r"\[\]\s*=\s*\{"
        r"(?P<values_block>[\s\S]*?)\s*\}\s*;",
        re.MULTILINE
    )
    # Pattern for names like "dim1KuoInit" (one or more digits for number)
    data_array_pattern_num_suffix_one_plus_digits = re.compile(
        r"const\s+(?P<type>\w[\w\s\:]*(?:_t)?)\s+"
        r"(?P<cxx_name>" + re.escape(data_array_prefix_cxx) + r"(?P<num_str>\d+)" + re.escape(data_array_suffix_cxx) + r")"
        r"\[\]\s*=\s*\{"
        r"(?P<values_block>[\s\S]*?)\s*\}\s*;",
        re.MULTILINE
    )

    # Determine which pattern to use based on prefix/suffix (heuristic)
    if data_array_suffix_cxx: # Likely "dim1KuoInit" pattern
        data_array_pattern_to_use = data_array_pattern_num_suffix_one_plus_digits
    else: # Likely "AltPrimitivePolynomialDegree01" pattern
        data_array_pattern_to_use = data_array_pattern_num_suffix_two_digits


    mojo_init_lines.append('        """Initialize all data arrays with their coefficient values."""')

    for match in data_array_pattern_to_use.finditer(cpp_code_string):
        raw_cxx_type = match.group("type").replace("const", "").strip() # Remove const for type mapping
        cxx_name = match.group("cxx_name")
        num_str = match.group("num_str") # This is the numeric part as a string
        values_block = match.group("values_block")

        values_no_comments = re.sub(r"/\*.*?\*/", "", values_block, flags=re.DOTALL)
        values_no_line_comments = re.sub(r"//.*", "", values_no_comments)
        values_list = [v.strip() for v in values_no_line_comments.replace('\n', ' ').split(',') if v.strip()]
        while values_list and not values_list[-1]: values_list.pop()

        # Construct Mojo name: data_array_base_mojo + num_str (e.g., degree01 or data_dim1)
        mojo_name = f"{data_array_base_mojo}{num_str}" 
        mojo_type_str = cpp_to_mojo_type(raw_cxx_type)
        array_size = len(values_list)
        values_str_for_mojo = ", ".join(values_list)

        data_arrays_info.append({
            'mojo_name': mojo_name,
            'cxx_name': cxx_name, # Store original C++ name for pointer mapping
            'num_str': num_str,   # Store the numeric part for sorting/reference
            'mojo_type': mojo_type_str,
            'size': array_size,
            'values_mojo': values_str_for_mojo
        })
        mojo_init_lines.append(f"        self.{mojo_name} = InlineArray[{mojo_type_str}, {array_size}]({values_str_for_mojo})")

    if data_arrays_info:
        mojo_init_lines.append('') 

    # --- Parse the main pointer array ---
    main_pointer_array_mojo_type = "SIMD[DType.si64,1]" # Default if parsing fails
    main_pointer_array_size_str = "UNKNOWN_SIZE" # Placeholder
    cxx_pointer_order = [] # List of C++ names in the order they appear in the pointer array

    # Regex for main pointer array. Example: const long *const AltPrimitivePolynomials[N_ALT_MAX_DEGREE]=
    # or const std::uint32_t * const Kuoinitializers[4925] =
    main_pointer_array_pattern = re.compile(
        r"const\s+(?P<base_type>\w[\w\s\:]*(?:_t)?)\s*\*\s*const\s+"
        r"(?P<array_name>" + re.escape(main_pointer_array_cxx) + r")"
        r"\[\s*(?P<size_specifier>\w+|\d+)\s*\]\s*=\s*\{" # Capture size (symbolic name or literal number)
        r"(?P<pointer_block>[\s\S]*?)\s*\}\s*;",
        re.MULTILINE
    )
    
    main_match = main_pointer_array_pattern.search(cpp_code_string)
    if main_match:
        raw_base_cxx_type = main_match.group("base_type").replace("const", "").strip()
        main_pointer_array_mojo_type = cpp_to_mojo_type(raw_base_cxx_type)
        main_pointer_array_size_str = main_match.group("size_specifier") # Could be a #define name or a number
        
        pointer_block_str = main_match.group("pointer_block")
        
        # Extract C++ names from the pointer block.
        # This regex should be general enough to find variable names.
        # It assumes variable names are typical C/C++ identifiers.
        cxx_ptr_name_pattern = re.compile(r"\b(" + re.escape(data_array_prefix_cxx) + r"\d+" + re.escape(data_array_suffix_cxx) + r")\b")
        cxx_pointer_order = cxx_ptr_name_pattern.findall(pointer_block_str)

        # If size_specifier was symbolic, but we found pointers, use count of pointers if more robust
        if not main_pointer_array_size_str.isdigit() and cxx_pointer_order:
            print(f"Info: Pointer array size was symbolic ('{main_pointer_array_size_str}'). "
                  f"Using count of found pointers ({len(cxx_pointer_order)}) instead for Mojo array size.")
            main_pointer_array_size_str = str(len(cxx_pointer_order))
        elif not cxx_pointer_order:
             print(f"Warning: No pointers found in the initializer block for {main_pointer_array_cxx}. "
                   f"Size '{main_pointer_array_size_str}' might be incorrect or block is empty/malformed.")


    # --- Generate the pointers initialization ---
    if cxx_pointer_order:
        mojo_init_lines.append("        // Create array of pointers for indexed access")
        init_line = (f"        self.{main_pointer_array_mojo} = "
                     f"InlineArray[UnsafePointer[{main_pointer_array_mojo_type}], {main_pointer_array_size_str}](")
        mojo_init_lines.append(init_line)
        
        ptr_initializer_list_mojo = []
        # Create a mapping from cxx_name to mojo_name for efficient lookup
        cxx_to_mojo_map = {arr['cxx_name']: arr['mojo_name'] for arr in data_arrays_info}

        for i, cxx_name_in_order in enumerate(cxx_pointer_order):
            mojo_equivalent_data_array = cxx_to_mojo_map.get(cxx_name_in_order)
            
            if mojo_equivalent_data_array:
                line = f"            self.{mojo_equivalent_data_array}.unsafe_ptr()"
            else:
                # This fallback is less likely to be correct if names are very different
                # but tries to make a guess based on the numeric part if the full cxx_name wasn't matched earlier.
                num_match = re.search(r"(\d+)", cxx_name_in_order) # Find any number in the C++ name
                if num_match:
                    num_part = num_match.group(1)
                    # If the original C++ name had a two-digit number format for this part
                    if data_array_pattern_to_use == data_array_pattern_num_suffix_two_digits and len(num_part) == 1:
                        num_part = f"0{num_part}" # Pad with zero for mojo name construction
                    
                    guessed_mojo_name = f"{data_array_base_mojo}{num_part}"
                    line = f"            self.{guessed_mojo_name}.unsafe_ptr() // Fallback guess, CXX: {cxx_name_in_order}"
                    print(f"Warning: Could not directly map C++ pointer '{cxx_name_in_order}'. Guessed Mojo var: '{guessed_mojo_name}'. Please verify.")
                else:
                    line = f"            // ERROR: CXX NAME {cxx_name_in_order} NOT PROPERLY MAPPED AND NO NUMBER FOUND"
                    print(f"Error: Could not map C++ pointer '{cxx_name_in_order}' and no numeric part found to make a guess.")


            if i < len(cxx_pointer_order) - 1:
                line += ","
            ptr_initializer_list_mojo.append(line)
        
        mojo_init_lines.extend(ptr_initializer_list_mojo)
        mojo_init_lines.append("        )")
    elif main_match: # Pointer array was declared but no pointers found in its block
        mojo_init_lines.append(f"        // WARNING: Pointer array '{main_pointer_array_cxx}' was declared but no pointers were found in its initializer block.")
        mojo_init_lines.append(f"        // self.{main_pointer_array_mojo} = InlineArray[UnsafePointer[{main_pointer_array_mojo_type}], {main_pointer_array_size_str}]()")
        mojo_init_lines.append(f"        // TODO: Manually fill the pointer initializers if this was not intended to be empty.")


    return "\n".join(mojo_init_lines)

if __name__ == "__main__":

    # Note: For brevity, I've truncated the full AltPrimitivePolynomialDegree03-07 in the test string. 
    # The script will only parse what's provided.


    cpp_kuo_code_input = """
const std::uint32_t dim1JoeKuoD5Init[]  =   {   1   ,0 };
            const std::uint32_t dim2JoeKuoD5Init[]  =   {   1   ,   3   ,0 };
            const std::uint32_t dim3JoeKuoD5Init[]  =   {   1   ,   3   ,   1   ,0 };
            const std::uint32_t dim4JoeKuoD5Init[]  =   {   1   ,   1   ,   1   ,0 };
            const std::uint32_t dim5JoeKuoD5Init[]  =   {   1   ,   1   ,   3   ,   3   ,0 };
            const std::uint32_t dim6JoeKuoD5Init[]  =   {   1   ,   3   ,   5   ,   13  ,0 };
            const std::uint32_t dim7JoeKuoD5Init[]  =   {   1   ,   1   ,   5   ,   5   ,   17  ,0 };
            const std::uint32_t dim8JoeKuoD5Init[]  =   {   1   ,   1   ,   5   ,   5   ,   5   ,0 };
            const std::uint32_t dim9JoeKuoD5Init[]  =   {   1   ,   1   ,   7   ,   11  ,   19  ,0 };
            const std::uint32_t dim10JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   1   ,   1   ,0 };
            const std::uint32_t dim11JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   1   ,   19  ,0 };
            const std::uint32_t dim12JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   5   ,   7   ,0 };
            const std::uint32_t dim13JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   13  ,   9   ,   53  ,0 };
            const std::uint32_t dim14JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   11  ,   1   ,   1   ,0 };
            const std::uint32_t dim15JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   7   ,   21  ,   51  ,0 };
            const std::uint32_t dim16JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   1   ,   5   ,0 };
            const std::uint32_t dim17JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   9   ,   9   ,   1   ,0 };
            const std::uint32_t dim18JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   5   ,   17  ,   61  ,0 };
            const std::uint32_t dim19JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   15  ,   29  ,   57  ,   87  ,0 };
            const std::uint32_t dim20JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   15  ,   3   ,   11  ,   17  ,0 };
            const std::uint32_t dim21JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   7   ,   5   ,   17  ,   65  ,0 };
            const std::uint32_t dim22JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   1   ,   25  ,   29  ,   49  ,0 };
            const std::uint32_t dim23JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   7   ,   15  ,   39  ,   119 ,0 };
            const std::uint32_t dim24JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   5   ,   19  ,   51  ,   61  ,0 };
            const std::uint32_t dim25JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   15  ,   11  ,   47  ,   15  ,0 };
            const std::uint32_t dim26JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   3   ,   29  ,   51  ,   51  ,0 };
            const std::uint32_t dim27JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   15  ,   19  ,   17  ,   13  ,0 };
            const std::uint32_t dim28JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   3   ,   17  ,   9   ,   93  ,0 };
            const std::uint32_t dim29JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   5   ,   7   ,   29  ,   111 ,0 };
            const std::uint32_t dim30JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   9   ,   25  ,   19  ,   105 ,0 };
            const std::uint32_t dim31JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   11  ,   21  ,   35  ,   107 ,0 };
            const std::uint32_t dim32JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   11  ,   19  ,   53  ,   25  ,0 };
            const std::uint32_t dim33JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   3   ,   27  ,   29  ,   31  ,0 };
            const std::uint32_t dim34JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   13  ,   27  ,   19  ,   61  ,0 };
            const std::uint32_t dim35JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   3   ,   25  ,   33  ,   105 ,0 };
            const std::uint32_t dim36JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   11  ,   27  ,   55  ,   1   ,0 };
            const std::uint32_t dim37JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   1   ,   9   ,   45  ,   97  ,   63  ,0 };
            const std::uint32_t dim38JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   9   ,   3   ,   17  ,   85  ,   213 ,0 };
            const std::uint32_t dim39JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   3   ,   31  ,   35  ,   93  ,   35  ,0 };
            const std::uint32_t dim40JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   9   ,   1   ,   63  ,   117 ,   35  ,0 };
            const std::uint32_t dim41JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   9   ,   21  ,   3   ,   53  ,   29  ,0 };
            const std::uint32_t dim42JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   9   ,   29  ,   33  ,   43  ,   181 ,0 };
            const std::uint32_t dim43JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   3   ,   21  ,   45  ,   121 ,   141 ,0 };
            const std::uint32_t dim44JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   13  ,   5   ,   49  ,   45  ,   77  ,0 };
            const std::uint32_t dim45JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   3   ,   1   ,   47  ,   37  ,   151 ,0 };
            const std::uint32_t dim46JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   5   ,   9   ,   51  ,   61  ,   95  ,0 };
            const std::uint32_t dim47JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   7   ,   31  ,   23  ,   81  ,   105 ,0 };
            const std::uint32_t dim48JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   15  ,   15  ,   9   ,   115 ,   55  ,0 };
            const std::uint32_t dim49JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   13  ,   15  ,   1   ,   87  ,   11  ,0 };
            const std::uint32_t dim50JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   1   ,   5   ,   9   ,   29  ,   241 ,0 };
            const std::uint32_t dim51JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   9   ,   19  ,   5   ,   115 ,   191 ,0 };
            const std::uint32_t dim52JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   1   ,   57  ,   107 ,   49  ,0 };
            const std::uint32_t dim53JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   7   ,   23  ,   21  ,   71  ,   187 ,   207 ,0 };
            const std::uint32_t dim54JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   5   ,   11  ,   35  ,   101 ,   7   ,   501 ,0 };
            const std::uint32_t dim55JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   15  ,   29  ,   5   ,   61  ,   205 ,   301 ,0 };
            const std::uint32_t dim56JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   13  ,   7   ,   39  ,   127 ,   243 ,   307 ,0 };
            const std::uint32_t dim57JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   13  ,   29  ,   9   ,   93  ,   187 ,   429 ,0 };
            const std::uint32_t dim58JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   11  ,   15  ,   35  ,   85  ,   159 ,   223 ,0 };
            const std::uint32_t dim59JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   1   ,   13  ,   3   ,   111 ,   17  ,   411 ,0 };
            const std::uint32_t dim60JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   7   ,   31  ,   21  ,   103 ,   175 ,   97  ,0 };
            const std::uint32_t dim61JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   11  ,   21  ,   63  ,   45  ,   29  ,0 };
            const std::uint32_t dim62JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   3   ,   13  ,   45  ,   53  ,   191 ,   455 ,0 };
            const std::uint32_t dim63JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   13  ,   11  ,   37  ,   65  ,   45  ,   371 ,0 };
            const std::uint32_t dim64JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   23  ,   9   ,   123 ,   97  ,   497 ,0 };
            const std::uint32_t dim65JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   7   ,   5   ,   13  ,   33  ,   169 ,   411 ,0 };
            const std::uint32_t dim66JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   13  ,   29  ,   61  ,   67  ,   1   ,   167 ,0 };
            const std::uint32_t dim67JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   3   ,   11  ,   21  ,   25  ,   87  ,   507 ,0 };
            const std::uint32_t dim68JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   9   ,   31  ,   37  ,   3   ,   89  ,   113 ,0 };
            const std::uint32_t dim69JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   11  ,   5   ,   11  ,   83  ,   85  ,   421 ,0 };
            const std::uint32_t dim70JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   7   ,   23  ,   9   ,   111 ,   135 ,   337 ,0 };
            const std::uint32_t dim71JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   15  ,   3   ,   39  ,   81  ,   249 ,   363 ,0 };
            const std::uint32_t dim72JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   15  ,   9   ,   49  ,   79  ,   103 ,   19  ,0 };
            const std::uint32_t dim73JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   1   ,   17  ,   31  ,   45  ,   205 ,   381 ,0 };
            const std::uint32_t dim74JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   1   ,   11  ,   45  ,   89  ,   1   ,   365 ,0 };
            const std::uint32_t dim75JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   7   ,   63  ,   55  ,   185 ,   373 ,0 };
            const std::uint32_t dim76JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   3   ,   17  ,   19  ,   23  ,   7   ,   265 ,0 };
            const std::uint32_t dim77JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   15  ,   13  ,   31  ,   53  ,   235 ,   309 ,0 };
            const std::uint32_t dim78JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   5   ,   1   ,   63  ,   73  ,   155 ,   33  ,0 };
            const std::uint32_t dim79JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   19  ,   57  ,   21  ,   45  ,   203 ,0 };
            const std::uint32_t dim80JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   9   ,   13  ,   27  ,   55  ,   215 ,   181 ,0 };
            const std::uint32_t dim81JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   3   ,   11  ,   39  ,   55  ,   219 ,   401 ,0 };
            const std::uint32_t dim82JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   7   ,   9   ,   13  ,   3   ,   181 ,   395 ,0 };
            const std::uint32_t dim83JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   15  ,   13  ,   19  ,   23  ,   145 ,   97  ,0 };
            const std::uint32_t dim84JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   15  ,   23  ,   15  ,   55  ,   3   ,   243 ,0 };
            const std::uint32_t dim85JoeKuoD5Init[] =   {   1   ,   1   ,   3   ,   15  ,   15  ,   5   ,   115 ,   169 ,   415 ,0 };
            const std::uint32_t dim86JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   15  ,   31  ,   15  ,   119 ,   89  ,   37  ,0 };
            const std::uint32_t dim87JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   3   ,   25  ,   23  ,   23  ,   133 ,   467 ,0 };
            const std::uint32_t dim88JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   15  ,   11  ,   7   ,   73  ,   209 ,   331 ,0 };
            const std::uint32_t dim89JoeKuoD5Init[] =   {   1   ,   3   ,   7   ,   11  ,   29  ,   51  ,   119 ,   105 ,   63  ,0 };
            const std::uint32_t dim90JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   9   ,   19  ,   21  ,   53  ,   211 ,   231 ,0 };
            const std::uint32_t dim91JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   1   ,   7   ,   23  ,   27  ,   67  ,   445 ,0 };
            const std::uint32_t dim92JoeKuoD5Init[] =   {   1   ,   1   ,   5   ,   15  ,   21  ,   53  ,   117 ,   229 ,   13  ,0 };
            const std::uint32_t dim93JoeKuoD5Init[] =   {   1   ,   3   ,   5   ,   11  ,   19  ,   55  ,   53  ,   13  ,   349 ,0 };
            const std::uint32_t dim94JoeKuoD5Init[] =   {   1   ,   3   ,   1   ,   9   ,   19  ,   25  ,   79  ,   55  ,   355 ,0 };
            const std::uint32_t dim95JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   5   ,   31  ,   27  ,   105 ,   63  ,   21  ,0 };
            const std::uint32_t dim96JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   15  ,   13  ,   37  ,   39  ,   13  ,   459 ,0 };
            const std::uint32_t dim97JoeKuoD5Init[] =   {   1   ,   1   ,   1   ,   7   ,   25  ,   61  ,   93  ,   195 ,   441 ,0 };
            const std::uint32_t dim98JoeKuoD5Init[] =   {   1   ,   3   ,   3   ,   3   ,   7   ,   35  ,   55  ,   103 ,   159 ,0 };
            const std::uint32_t dim99JoeKuoD5Init[] =   {   1   ,   1   ,   7   ,   11  ,   7   ,   33  ,   49  ,   113 ,   331 ,0 };
            const std::uint32_t dim100JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   1   ,   31  ,   35  ,   63  ,   465 ,0 };
            const std::uint32_t dim101JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   13  ,   43  ,   83  ,   177 ,   461 ,   747 ,0 };
            const std::uint32_t dim102JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   21  ,   5   ,   19  ,   135 ,   483 ,   181 ,0 };
            const std::uint32_t dim103JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   25  ,   3   ,   37  ,   147 ,   483 ,   743 ,0 };
            const std::uint32_t dim104JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   1   ,   1   ,   101 ,   163 ,   165 ,   957 ,0 };
            const std::uint32_t dim105JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   15  ,   41  ,   117 ,   7   ,   71  ,   357 ,0 };
            const std::uint32_t dim106JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   27  ,   11  ,   55  ,   5   ,   11  ,   863 ,0 };
            const std::uint32_t dim107JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   27  ,   43  ,   51  ,   211 ,   265 ,   403 ,0 };
            const std::uint32_t dim108JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   31  ,   35  ,   61  ,   43  ,   223 ,   441 ,0 };
            const std::uint32_t dim109JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   19  ,   61  ,   59  ,   63  ,   401 ,   767 ,0 };
            const std::uint32_t dim110JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   23  ,   39  ,   83  ,   249 ,   129 ,   843 ,0 };
            const std::uint32_t dim111JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   1   ,   49  ,   61  ,   115 ,   289 ,   85  ,0 };
            const std::uint32_t dim112JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   7   ,   17  ,   35  ,   95  ,   235 ,   49  ,0 };
            const std::uint32_t dim113JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   9   ,   9   ,   91  ,   141 ,   305 ,   955 ,0 };
            const std::uint32_t dim114JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   17  ,   3   ,   77  ,   95  ,   507 ,   627 ,0 };
            const std::uint32_t dim115JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   31  ,   43  ,   31  ,   217 ,   67  ,   853 ,0 };
            const std::uint32_t dim116JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   17  ,   33  ,   31  ,   91  ,   465 ,   209 ,0 };
            const std::uint32_t dim117JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   31  ,   41  ,   101 ,   95  ,   431 ,   203 ,0 };
            const std::uint32_t dim118JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   23  ,   45  ,   123 ,   111 ,   457 ,   655 ,0 };
            const std::uint32_t dim119JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   9   ,   27  ,   37  ,   195 ,   11  ,   99  ,0 };
            const std::uint32_t dim120JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   7   ,   39  ,   81  ,   171 ,   97  ,   775 ,0 };
            const std::uint32_t dim121JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   3   ,   27  ,   93  ,   149 ,   321 ,   537 ,0 };
            const std::uint32_t dim122JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   13  ,   3   ,   59  ,   137 ,   505 ,   395 ,0 };
            const std::uint32_t dim123JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   15  ,   53  ,   77  ,   235 ,   439 ,   829 ,0 };
            const std::uint32_t dim124JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   25  ,   61  ,   65  ,   53  ,   207 ,   891 ,0 };
            const std::uint32_t dim125JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   29  ,   39  ,   67  ,   203 ,   495 ,   795 ,0 };
            const std::uint32_t dim126JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   15  ,   17  ,   119 ,   83  ,   411 ,   1015    ,0 };
            const std::uint32_t dim127JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   13  ,   37  ,   69  ,   147 ,   141 ,   229 ,0 };
            const std::uint32_t dim128JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   11  ,   31  ,   73  ,   99  ,   133 ,   45  ,0 };
            const std::uint32_t dim129JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   31  ,   49  ,   51  ,   45  ,   27  ,   415 ,0 };
            const std::uint32_t dim130JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   23  ,   19  ,   85  ,   17  ,   41  ,   625 ,0 };
            const std::uint32_t dim131JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   3   ,   37  ,   9   ,   57  ,   59  ,   383 ,0 };
            const std::uint32_t dim132JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   19  ,   53  ,   11  ,   215 ,   391 ,   51  ,0 };
            const std::uint32_t dim133JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   17  ,   1   ,   53  ,   89  ,   291 ,   91  ,0 };
            const std::uint32_t dim134JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   5   ,   33  ,   69  ,   29  ,   281 ,   13  ,0 };
            const std::uint32_t dim135JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   21  ,   61  ,   61  ,   69  ,   395 ,   785 ,0 };
            const std::uint32_t dim136JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   25  ,   51  ,   27  ,   11  ,   375 ,   865 ,0 };
            const std::uint32_t dim137JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   11  ,   47  ,   45  ,   85  ,   507 ,   11  ,0 };
            const std::uint32_t dim138JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   17  ,   53  ,   101 ,   57  ,   213 ,   795 ,0 };
            const std::uint32_t dim139JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   15  ,   19  ,   117 ,   213 ,   397 ,   343 ,0 };
            const std::uint32_t dim140JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   9   ,   19  ,   27  ,   23  ,   205 ,   707 ,0 };
            const std::uint32_t dim141JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   11  ,   51  ,   1   ,   3   ,   63  ,   483 ,0 };
            const std::uint32_t dim142JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   27  ,   49  ,   97  ,   247 ,   273 ,   785 ,0 };
            const std::uint32_t dim143JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   31  ,   3   ,   43  ,   199 ,   81  ,   317 ,0 };
            const std::uint32_t dim144JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   17  ,   3   ,   101 ,   13  ,   131 ,   631 ,0 };
            const std::uint32_t dim145JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   25  ,   23  ,   17  ,   145 ,   247 ,   889 ,0 };
            const std::uint32_t dim146JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   17  ,   5   ,   11  ,   133 ,   19  ,   507 ,0 };
            const std::uint32_t dim147JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   31  ,   53  ,   39  ,   107 ,   183 ,   335 ,0 };
            const std::uint32_t dim148JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   3   ,   19  ,   39  ,   155 ,   477 ,   833 ,0 };
            const std::uint32_t dim149JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   31  ,   7   ,   5   ,   5   ,   399 ,   831 ,0 };
            const std::uint32_t dim150JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   19  ,   37  ,   89  ,   243 ,   131 ,   901 ,0 };
            const std::uint32_t dim151JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   23  ,   3   ,   127 ,   213 ,   97  ,   325 ,0 };
            const std::uint32_t dim152JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   23  ,   27  ,   7   ,   161 ,   307 ,   451 ,0 };
            const std::uint32_t dim153JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   5   ,   25  ,   23  ,   103 ,   59  ,   431 ,0 };
            const std::uint32_t dim154JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   3   ,   43  ,   121 ,   117 ,   33  ,   231 ,0 };
            const std::uint32_t dim155JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   11  ,   61  ,   73  ,   231 ,   225 ,   97  ,0 };
            const std::uint32_t dim156JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   1   ,   9   ,   61  ,   3   ,   407 ,   425 ,0 };
            const std::uint32_t dim157JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   1   ,   25  ,   95  ,   161 ,   387 ,   379 ,0 };
            const std::uint32_t dim158JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   15  ,   53  ,   55  ,   107 ,   425 ,   629 ,0 };
            const std::uint32_t dim159JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   31  ,   59  ,   97  ,   99  ,   339 ,   417 ,0 };
            const std::uint32_t dim160JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   9   ,   5   ,   7   ,   157 ,   401 ,   155 ,0 };
            const std::uint32_t dim161JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   31  ,   15  ,   37  ,   253 ,   93  ,   149 ,   1255    ,0 };
            const std::uint32_t dim162JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   11  ,   61  ,   65  ,   71  ,   53  ,   929 ,   1153    ,0 };
            const std::uint32_t dim163JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   13  ,   25  ,   93  ,   55  ,   55  ,   923 ,   601 ,0 };
            const std::uint32_t dim164JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   21  ,   43  ,   71  ,   115 ,   253 ,   953 ,   1455    ,0 };
            const std::uint32_t dim165JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   3   ,   31  ,   115 ,   213 ,   39  ,   589 ,   1029    ,0 };
            const std::uint32_t dim166JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   7   ,   59  ,   31  ,   87  ,   233 ,   75  ,   365 ,0 };
            const std::uint32_t dim167JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   13  ,   27  ,   55  ,   117 ,   327 ,   465 ,   1735    ,0 };
            const std::uint32_t dim168JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   25  ,   9   ,   125 ,   247 ,   81  ,   437 ,   483 ,0 };
            const std::uint32_t dim169JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   27  ,   39  ,   27  ,   57  ,   45  ,   263 ,   281 ,0 };
            const std::uint32_t dim170JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   29  ,   5   ,   73  ,   231 ,   97  ,   773 ,   1349    ,0 };
            const std::uint32_t dim171JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   25  ,   27  ,   81  ,   87  ,   91  ,   169 ,   235 ,0 };
            const std::uint32_t dim172JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   19  ,   61  ,   17  ,   175 ,   253 ,   673 ,   175 ,0 };
            const std::uint32_t dim173JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   17  ,   43  ,   65  ,   245 ,   125 ,   137 ,   1475    ,0 };
            const std::uint32_t dim174JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   15  ,   57  ,   39  ,   151 ,   197 ,   529 ,   393 ,0 };
            const std::uint32_t dim175JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   29  ,   41  ,   93  ,   47  ,   375 ,   729 ,   709 ,0 };
            const std::uint32_t dim176JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   13  ,   35  ,   49  ,   197 ,   107 ,   381 ,   1531    ,0 };
            const std::uint32_t dim177JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   15  ,   35  ,   105 ,   105 ,   259 ,   201 ,   317 ,0 };
            const std::uint32_t dim178JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   13  ,   23  ,   89  ,   203 ,   335 ,   1003    ,   107 ,0 };
            const std::uint32_t dim179JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   25  ,   25  ,   7   ,   145 ,   213 ,   845 ,   949 ,0 };
            const std::uint32_t dim180JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   23  ,   11  ,   101 ,   59  ,   57  ,   261 ,   1627    ,0 };
            const std::uint32_t dim181JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   23  ,   63  ,   43  ,   137 ,   49  ,   249 ,   1369    ,0 };
            const std::uint32_t dim182JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   25  ,   3   ,   81  ,   157 ,   511 ,   725 ,   2027    ,0 };
            const std::uint32_t dim183JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   5   ,   37  ,   33  ,   7   ,   287 ,   307 ,   147 ,0 };
            const std::uint32_t dim184JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   27  ,   19  ,   93  ,   173 ,   145 ,   821 ,   139 ,0 };
            const std::uint32_t dim185JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   23  ,   61  ,   123 ,   85  ,   375 ,   699 ,   229 ,0 };
            const std::uint32_t dim186JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   25  ,   21  ,   127 ,   53  ,   247 ,   1005    ,   831 ,0 };
            const std::uint32_t dim187JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   25  ,   39  ,   27  ,   247 ,   319 ,   659 ,   1453    ,0 };
            const std::uint32_t dim188JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   31  ,   45  ,   67  ,   195 ,   11  ,   481 ,   83  ,0 };
            const std::uint32_t dim189JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   27  ,   61  ,   5   ,   173 ,   353 ,   733 ,   1189    ,0 };
            const std::uint32_t dim190JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   23  ,   49  ,   119 ,   145 ,   285 ,   873 ,   641 ,0 };
            const std::uint32_t dim191JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   1   ,   17  ,   119 ,   121 ,   203 ,   483 ,   1601    ,0 };
            const std::uint32_t dim192JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   21  ,   35  ,   121 ,   11  ,   213 ,   93  ,   77  ,0 };
            const std::uint32_t dim193JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   7   ,   5   ,   27  ,   153 ,   223 ,   831 ,   679 ,0 };
            const std::uint32_t dim194JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   1   ,   39  ,   39  ,   233 ,   483 ,   667 ,   1367    ,0 };
            const std::uint32_t dim195JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   19  ,   51  ,   21  ,   209 ,   381 ,   787 ,   1451    ,0 };
            const std::uint32_t dim196JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   15  ,   9   ,   29  ,   225 ,   225 ,   389 ,   1075    ,0 };
            const std::uint32_t dim197JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   13  ,   57  ,   55  ,   229 ,   279 ,   1019    ,   1491    ,0 };
            const std::uint32_t dim198JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   19  ,   19  ,   35  ,   15  ,   335 ,   685 ,   1987    ,0 };
            const std::uint32_t dim199JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   1   ,   5   ,   3   ,   29  ,   19  ,   363 ,   247 ,0 };
            const std::uint32_t dim200JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   13  ,   17  ,   17  ,   253 ,   365 ,   397 ,   1643    ,0 };
            const std::uint32_t dim201JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   25  ,   23  ,   81  ,   243 ,   343 ,   441 ,   1675    ,0 };
            const std::uint32_t dim202JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   15  ,   51  ,   23  ,   213 ,   235 ,   997 ,   1205    ,0 };
            const std::uint32_t dim203JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   5   ,   39  ,   99  ,   165 ,   331 ,   795 ,   803 ,0 };
            const std::uint32_t dim204JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   31  ,   63  ,   109 ,   171 ,   151 ,   269 ,   581 ,0 };
            const std::uint32_t dim205JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   25  ,   13  ,   41  ,   75  ,   411 ,   425 ,   267 ,0 };
            const std::uint32_t dim206JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   1   ,   31  ,   49  ,   113 ,   473 ,   677 ,   395 ,0 };
            const std::uint32_t dim207JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   23  ,   43  ,   111 ,   171 ,   489 ,   949 ,   1681    ,0 };
            const std::uint32_t dim208JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   5   ,   37  ,   67  ,   23  ,   115 ,   909 ,   853 ,0 };
            const std::uint32_t dim209JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   27  ,   35  ,   63  ,   45  ,   481 ,   571 ,   793 ,0 };
            const std::uint32_t dim210JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   11  ,   45  ,   53  ,   225 ,   147 ,   935 ,   1189    ,0 };
            const std::uint32_t dim211JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   15  ,   17  ,   77  ,   59  ,   169 ,   831 ,   163 ,0 };
            const std::uint32_t dim212JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   7   ,   29  ,   85  ,   19  ,   313 ,   35  ,   401 ,0 };
            const std::uint32_t dim213JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   3   ,   1   ,   45  ,   139 ,   17  ,   847 ,   1309    ,0 };
            const std::uint32_t dim214JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   25  ,   1   ,   117 ,   185 ,   291 ,   251 ,   1049    ,0 };
            const std::uint32_t dim215JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   27  ,   63  ,   33  ,   161 ,   181 ,   79  ,   667 ,0 };
            const std::uint32_t dim216JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   9   ,   63  ,   91  ,   207 ,   329 ,   3   ,   1155    ,0 };
            const std::uint32_t dim217JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   3   ,   59  ,   39  ,   37  ,   231 ,   993 ,   1147    ,0 };
            const std::uint32_t dim218JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   7   ,   41  ,   85  ,   223 ,   407 ,   403 ,   573 ,0 };
            const std::uint32_t dim219JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   15  ,   51  ,   1   ,   191 ,   123 ,   103 ,   1201    ,0 };
            const std::uint32_t dim220JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   31  ,   9   ,   83  ,   231 ,   419 ,   109 ,   1455    ,0 };
            const std::uint32_t dim221JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   13  ,   39  ,   89  ,   9   ,   237 ,   185 ,   1113    ,0 };
            const std::uint32_t dim222JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   1   ,   43  ,   121 ,   241 ,   165 ,   263 ,   1205    ,0 };
            const std::uint32_t dim223JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   21  ,   3   ,   61  ,   219 ,   49  ,   733 ,   25  ,0 };
            const std::uint32_t dim224JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   31  ,   27  ,   121 ,   61  ,   447 ,   401 ,   529 ,0 };
            const std::uint32_t dim225JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   27  ,   47  ,   85  ,   5   ,   305 ,   763 ,   1255    ,0 };
            const std::uint32_t dim226JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   13  ,   41  ,   9   ,   51  ,   195 ,   103 ,   983 ,0 };
            const std::uint32_t dim227JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   1   ,   27  ,   65  ,   91  ,   61  ,   591 ,   2039    ,0 };
            const std::uint32_t dim228JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   15  ,   19  ,   107 ,   197 ,   121 ,   879 ,   771 ,0 };
            const std::uint32_t dim229JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   19  ,   53  ,   9   ,   3   ,   67  ,   893 ,   1817    ,0 };
            const std::uint32_t dim230JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   11  ,   63  ,   53  ,   247 ,   65  ,   681 ,   1721    ,0 };
            const std::uint32_t dim231JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   25  ,   47  ,   91  ,   55  ,   471 ,   731 ,   939 ,0 };
            const std::uint32_t dim232JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   7   ,   45  ,   121 ,   69  ,   423 ,   599 ,   2027    ,0 };
            const std::uint32_t dim233JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   23  ,   7   ,   43  ,   179 ,   511 ,   571 ,   1707    ,0 };
            const std::uint32_t dim234JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   17  ,   11  ,   69  ,   13  ,   303 ,   299 ,   653 ,0 };
            const std::uint32_t dim235JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   7   ,   29  ,   69  ,   237 ,   237 ,   425 ,   1413    ,0 };
            const std::uint32_t dim236JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   19  ,   31  ,   55  ,   55  ,   225 ,   943 ,   1027    ,0 };
            const std::uint32_t dim237JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   25  ,   9   ,   9   ,   29  ,   485 ,   885 ,   1229    ,0 };
            const std::uint32_t dim238JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   7   ,   11  ,   73  ,   151 ,   17  ,   669 ,   773 ,0 };
            const std::uint32_t dim239JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   25  ,   13  ,   51  ,   53  ,   411 ,   555 ,   795 ,0 };
            const std::uint32_t dim240JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   21  ,   33  ,   7   ,   113 ,   325 ,   593 ,   1647    ,0 };
            const std::uint32_t dim241JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   3   ,   13  ,   83  ,   205 ,   153 ,   7   ,   1181    ,0 };
            const std::uint32_t dim242JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   1   ,   55  ,   91  ,   17  ,   383 ,   453 ,   1749    ,0 };
            const std::uint32_t dim243JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   5   ,   13  ,   91  ,   19  ,   241 ,   569 ,   291 ,0 };
            const std::uint32_t dim244JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   13  ,   19  ,   109 ,   195 ,   17  ,   203 ,   473 ,0 };
            const std::uint32_t dim245JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   17  ,   17  ,   43  ,   201 ,   297 ,   159 ,   685 ,0 };
            const std::uint32_t dim246JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   15  ,   33  ,   91  ,   53  ,   337 ,   237 ,   1063    ,0 };
            const std::uint32_t dim247JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   13  ,   15  ,   59  ,   115 ,   457 ,   169 ,   29  ,0 };
            const std::uint32_t dim248JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   21  ,   51  ,   41  ,   49  ,   467 ,   171 ,   301 ,0 };
            const std::uint32_t dim249JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   19  ,   57  ,   27  ,   57  ,   119 ,   183 ,   1519    ,0 };
            const std::uint32_t dim250JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   19  ,   21  ,   117 ,   35  ,   43  ,   829 ,   1817    ,0 };
            const std::uint32_t dim251JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   9   ,   27  ,   127 ,   233 ,   229 ,   467 ,   2033    ,0 };
            const std::uint32_t dim252JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   7   ,   21  ,   113 ,   23  ,   15  ,   43  ,   375 ,0 };
            const std::uint32_t dim253JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   11  ,   21  ,   13  ,   87  ,   57  ,   805 ,   1529    ,0 };
            const std::uint32_t dim254JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   3   ,   39  ,   115 ,   179 ,   199 ,   907 ,   1487    ,0 };
            const std::uint32_t dim255JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   17  ,   17  ,   83  ,   23  ,   421 ,   813 ,   29  ,0 };
            const std::uint32_t dim256JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   29  ,   39  ,   81  ,   69  ,   339 ,   495 ,   281 ,0 };
            const std::uint32_t dim257JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   27  ,   39  ,   9   ,   233 ,   19  ,   663 ,   57  ,0 };
            const std::uint32_t dim258JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   17  ,   7   ,   17  ,   39  ,   299 ,   97  ,   1329    ,0 };
            const std::uint32_t dim259JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   9   ,   27  ,   5   ,   245 ,   477 ,   591 ,   1021    ,0 };
            const std::uint32_t dim260JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   9   ,   37  ,   19  ,   141 ,   201 ,   57  ,   1117    ,0 };
            const std::uint32_t dim261JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   7   ,   27  ,   33  ,   235 ,   247 ,   701 ,   1293    ,0 };
            const std::uint32_t dim262JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   17  ,   25  ,   81  ,   213 ,   457 ,   877 ,   741 ,0 };
            const std::uint32_t dim263JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   15  ,   47  ,   113 ,   29  ,   111 ,   913 ,   1695    ,0 };
            const std::uint32_t dim264JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   5   ,   53  ,   119 ,   215 ,   163 ,   933 ,   1447    ,0 };
            const std::uint32_t dim265JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   15  ,   27  ,   111 ,   19  ,   231 ,   287 ,   1439    ,0 };
            const std::uint32_t dim266JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   27  ,   29  ,   35  ,   109 ,   249 ,   989 ,   1837    ,0 };
            const std::uint32_t dim267JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   29  ,   35  ,   51  ,   241 ,   509 ,   163 ,   831 ,0 };
            const std::uint32_t dim268JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   7   ,   59  ,   43  ,   111 ,   119 ,   639 ,   899 ,0 };
            const std::uint32_t dim269JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   15  ,   47  ,   95  ,   219 ,   377 ,   899 ,   535 ,0 };
            const std::uint32_t dim270JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   3   ,   19  ,   115 ,   59  ,   143 ,   13  ,   701 ,0 };
            const std::uint32_t dim271JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   5   ,   17  ,   17  ,   91  ,   223 ,   923 ,   1299    ,0 };
            const std::uint32_t dim272JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   21  ,   21  ,   85  ,   127 ,   253 ,   271 ,   725 ,0 };
            const std::uint32_t dim273JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   9   ,   11  ,   113 ,   67  ,   509 ,   697 ,   1163    ,0 };
            const std::uint32_t dim274JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   13  ,   53  ,   15  ,   221 ,   253 ,   219 ,   1839    ,0 };
            const std::uint32_t dim275JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   31  ,   63  ,   85  ,   171 ,   345 ,   243 ,   711 ,0 };
            const std::uint32_t dim276JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   25  ,   13  ,   65  ,   91  ,   441 ,   609 ,   1751    ,0 };
            const std::uint32_t dim277JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   23  ,   1   ,   15  ,   83  ,   115 ,   367 ,   735 ,0 };
            const std::uint32_t dim278JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   11  ,   15  ,   41  ,   1   ,   437 ,   231 ,   1529    ,0 };
            const std::uint32_t dim279JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   29  ,   11  ,   89  ,   133 ,   473 ,   811 ,   87  ,0 };
            const std::uint32_t dim280JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   15  ,   39  ,   97  ,   197 ,   475 ,   105 ,   527 ,0 };
            const std::uint32_t dim281JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   9   ,   17  ,   21  ,   167 ,   255 ,   341 ,   765 ,0 };
            const std::uint32_t dim282JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   23  ,   47  ,   121 ,   219 ,   343 ,   169 ,   1147    ,0 };
            const std::uint32_t dim283JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   3   ,   57  ,   27  ,   147 ,   383 ,   157 ,   1851    ,0 };
            const std::uint32_t dim284JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   25  ,   17  ,   35  ,   123 ,   371 ,   281 ,   881 ,0 };
            const std::uint32_t dim285JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   11  ,   11  ,   21  ,   5   ,   53  ,   155 ,   1811    ,0 };
            const std::uint32_t dim286JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   31  ,   27  ,   117 ,   169 ,   389 ,   651 ,   1513    ,0 };
            const std::uint32_t dim287JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   31  ,   15  ,   103 ,   59  ,   73  ,   575 ,   1597    ,0 };
            const std::uint32_t dim288JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   15  ,   5   ,   17  ,   183 ,   471 ,   561 ,   607 ,0 };
            const std::uint32_t dim289JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   9   ,   39  ,   25  ,   87  ,   171 ,   559 ,   481 ,0 };
            const std::uint32_t dim290JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   17  ,   61  ,   101 ,   255 ,   147 ,   481 ,   661 ,0 };
            const std::uint32_t dim291JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   17  ,   9   ,   119 ,   31  ,   177 ,   475 ,   1243    ,0 };
            const std::uint32_t dim292JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   27  ,   45  ,   111 ,   229 ,   201 ,   927 ,   339 ,0 };
            const std::uint32_t dim293JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   9   ,   25  ,   23  ,   91  ,   453 ,   861 ,   1919    ,0 };
            const std::uint32_t dim294JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   7   ,   57  ,   93  ,   75  ,   223 ,   63  ,   7   ,0 };
            const std::uint32_t dim295JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   7   ,   29  ,   71  ,   197 ,   405 ,   401 ,   585 ,0 };
            const std::uint32_t dim296JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   11  ,   11  ,   7   ,   157 ,   1   ,   105 ,   473 ,0 };
            const std::uint32_t dim297JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   29  ,   3   ,   127 ,   243 ,   93  ,   123 ,   1041    ,0 };
            const std::uint32_t dim298JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   25  ,   55  ,   13  ,   243 ,   37  ,   565 ,   1167    ,0 };
            const std::uint32_t dim299JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   31  ,   29  ,   75  ,   61  ,   43  ,   159 ,   443 ,0 };
            const std::uint32_t dim300JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   15  ,   63  ,   43  ,   251 ,   97  ,   141 ,   791 ,0 };
            const std::uint32_t dim301JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   27  ,   43  ,   17  ,   49  ,   109 ,   777 ,   1999    ,0 };
            const std::uint32_t dim302JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   25  ,   5   ,   15  ,   145 ,   75  ,   855 ,   771 ,0 };
            const std::uint32_t dim303JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   7   ,   27  ,   3   ,   221 ,   451 ,   533 ,   1059    ,0 };
            const std::uint32_t dim304JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   11  ,   61  ,   53  ,   33  ,   217 ,   967 ,   177 ,0 };
            const std::uint32_t dim305JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   1   ,   7   ,   85  ,   105 ,   417 ,   87  ,   417 ,0 };
            const std::uint32_t dim306JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   13  ,   59  ,   11  ,   219 ,   363 ,   481 ,   893 ,0 };
            const std::uint32_t dim307JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   27  ,   23  ,   85  ,   239 ,   343 ,   43  ,   1597    ,0 };
            const std::uint32_t dim308JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   29  ,   5   ,   127 ,   49  ,   223 ,   797 ,   2003    ,0 };
            const std::uint32_t dim309JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   29  ,   61  ,   21  ,   191 ,   157 ,   355 ,   2033    ,0 };
            const std::uint32_t dim310JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   5   ,   49  ,   53  ,   207 ,   121 ,   451 ,   319 ,0 };
            const std::uint32_t dim311JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   9   ,   7   ,   111 ,   153 ,   151 ,   395 ,   1389    ,0 };
            const std::uint32_t dim312JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   25  ,   45  ,   113 ,   99  ,   263 ,   561 ,   1181    ,0 };
            const std::uint32_t dim313JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   13  ,   27  ,   77  ,   1   ,   109 ,   741 ,   59  ,0 };
            const std::uint32_t dim314JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   15  ,   57  ,   43  ,   7   ,   507 ,   885 ,   747 ,0 };
            const std::uint32_t dim315JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   25  ,   7   ,   45  ,   147 ,   375 ,   975 ,   619 ,0 };
            const std::uint32_t dim316JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   13  ,   11  ,   107 ,   81  ,   199 ,   11  ,   1267    ,0 };
            const std::uint32_t dim317JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   15  ,   11  ,   113 ,   61  ,   425 ,   43  ,   1889    ,0 };
            const std::uint32_t dim318JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   29  ,   11  ,   123 ,   237 ,   173 ,   249 ,   1091    ,0 };
            const std::uint32_t dim319JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   29  ,   13  ,   21  ,   159 ,   149 ,   379 ,   1665    ,0 };
            const std::uint32_t dim320JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   13  ,   53  ,   23  ,   47  ,   115 ,   183 ,   577 ,0 };
            const std::uint32_t dim321JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   11  ,   49  ,   77  ,   81  ,   193 ,   133 ,   489 ,0 };
            const std::uint32_t dim322JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   7   ,   27  ,   53  ,   187 ,   347 ,   211 ,   233 ,0 };
            const std::uint32_t dim323JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   15  ,   17  ,   45  ,   75  ,   449 ,   971 ,   1123    ,0 };
            const std::uint32_t dim324JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   25  ,   21  ,   109 ,   71  ,   439 ,   439 ,   1397    ,0 };
            const std::uint32_t dim325JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   9   ,   47  ,   117 ,   117 ,   165 ,   531 ,   271 ,0 };
            const std::uint32_t dim326JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   11  ,   5   ,   31  ,   199 ,   159 ,   87  ,   1729    ,0 };
            const std::uint32_t dim327JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   27  ,   29  ,   17  ,   237 ,   175 ,   881 ,   989 ,0 };
            const std::uint32_t dim328JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   25  ,   63  ,   19  ,   159 ,   409 ,   247 ,   683 ,0 };
            const std::uint32_t dim329JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   15  ,   39  ,   101 ,   129 ,   253 ,   487 ,   719 ,0 };
            const std::uint32_t dim330JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   7   ,   13  ,   107 ,   249 ,   331 ,   553 ,   1199    ,0 };
            const std::uint32_t dim331JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   5   ,   51  ,   81  ,   37  ,   349 ,   561 ,   295 ,0 };
            const std::uint32_t dim332JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   27  ,   61  ,   49  ,   89  ,   379 ,   67  ,   1063    ,0 };
            const std::uint32_t dim333JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   15  ,   37  ,   119 ,   141 ,   81  ,   341 ,   2003    ,0 };
            const std::uint32_t dim334JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   29  ,   31  ,   29  ,   143 ,   463 ,   399 ,   1345    ,0 };
            const std::uint32_t dim335JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   29  ,   35  ,   29  ,   233 ,   499 ,   503 ,   903 ,0 };
            const std::uint32_t dim336JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   29  ,   23  ,   127 ,   185 ,   77  ,   555 ,   1311    ,0 };
            const std::uint32_t dim337JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   23  ,   3   ,   111 ,   159 ,   503 ,   889 ,   1043    ,   1153    ,0 };
            const std::uint32_t dim338JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   13  ,   41  ,   109 ,   133 ,   81  ,   525 ,   2027    ,   3059    ,0 };
            const std::uint32_t dim339JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   29  ,   53  ,   111 ,   129 ,   399 ,   479 ,   467 ,   363 ,0 };
            const std::uint32_t dim340JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   5   ,   7   ,   9   ,   21  ,   391 ,   851 ,   575 ,   1317    ,0 };
            const std::uint32_t dim341JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   19  ,   59  ,   91  ,   133 ,   403 ,   71  ,   1895    ,   3029    ,0 };
            const std::uint32_t dim342JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   21  ,   29  ,   113 ,   109 ,   463 ,   251 ,   393 ,   3169    ,0 };
            const std::uint32_t dim343JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   25  ,   3   ,   47  ,   195 ,   223 ,   1003    ,   947 ,   121 ,0 };
            const std::uint32_t dim344JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   31  ,   61  ,   63  ,   31  ,   49  ,   907 ,   389 ,   3713    ,0 };
            const std::uint32_t dim345JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   13  ,   19  ,   55  ,   87  ,   489 ,   665 ,   945 ,   2081    ,0 };
            const std::uint32_t dim346JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   23  ,   5   ,   39  ,   19  ,   355 ,   399 ,   929 ,   3077    ,0 };
            const std::uint32_t dim347JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   7   ,   59  ,   43  ,   69  ,   285 ,   753 ,   75  ,   2261    ,0 };
            const std::uint32_t dim348JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   27  ,   45  ,   29  ,   181 ,   347 ,   863 ,   1421    ,   2077    ,0 };
            const std::uint32_t dim349JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   7   ,   27  ,   77  ,   67  ,   399 ,   919 ,   917 ,   1465    ,0 };
            const std::uint32_t dim350JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   11  ,   41  ,   17  ,   65  ,   495 ,   643 ,   1641    ,   323 ,0 };
            const std::uint32_t dim351JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   9   ,   37  ,   107 ,   171 ,   189 ,   405 ,   2005    ,   2811    ,0 };
            const std::uint32_t dim352JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   3   ,   63  ,   51  ,   27  ,   479 ,   571 ,   575 ,   2859    ,0 };
            const std::uint32_t dim353JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   29  ,   23  ,   89  ,   7   ,   265 ,   41  ,   481 ,   2177    ,0 };
            const std::uint32_t dim354JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   29  ,   15  ,   79  ,   217 ,   411 ,   867 ,   49  ,   469 ,0 };
            const std::uint32_t dim355JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   3   ,   27  ,   69  ,   177 ,   291 ,   965 ,   637 ,   3629    ,0 };
            const std::uint32_t dim356JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   11  ,   45  ,   83  ,   63  ,   275 ,   851 ,   779 ,   2615    ,0 };
            const std::uint32_t dim357JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   1   ,   27  ,   89  ,   153 ,   355 ,   811 ,   515 ,   1541    ,0 };
            const std::uint32_t dim358JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   1   ,   21  ,   75  ,   5   ,   255 ,   813 ,   1347    ,   2301    ,0 };
            const std::uint32_t dim359JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   9   ,   49  ,   3   ,   203 ,   505 ,   591 ,   713 ,   2893    ,0 };
            const std::uint32_t dim360JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   1   ,   51  ,   11  ,   161 ,   41  ,   17  ,   435 ,   3045    ,0 };
            const std::uint32_t dim361JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   15  ,   23  ,   115 ,   73  ,   343 ,   985 ,   1559    ,   1615    ,0 };
            const std::uint32_t dim362JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   9   ,   43  ,   17  ,   187 ,   311 ,   749 ,   1841    ,   609 ,0 };
            const std::uint32_t dim363JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   13  ,   3   ,   113 ,   83  ,   287 ,   931 ,   399 ,   2143    ,0 };
            const std::uint32_t dim364JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   17  ,   11  ,   99  ,   235 ,   313 ,   293 ,   2005    ,   2557    ,0 };
            const std::uint32_t dim365JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   7   ,   57  ,   79  ,   225 ,   415 ,   749 ,   1243    ,   1303    ,0 };
            const std::uint32_t dim366JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   21  ,   37  ,   55  ,   53  ,   389 ,   141 ,   1231    ,   1639    ,0 };
            const std::uint32_t dim367JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   15  ,   37  ,   83  ,   219 ,   471 ,   751 ,   1241    ,   269 ,0 };
            const std::uint32_t dim368JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   7   ,   51  ,   37  ,   81  ,   97  ,   857 ,   1431    ,   883 ,0 };
            const std::uint32_t dim369JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   27  ,   31  ,   29  ,   223 ,   439 ,   25  ,   379 ,   3721    ,0 };
            const std::uint32_t dim370JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   13  ,   11  ,   55  ,   127 ,   493 ,   493 ,   143 ,   1595    ,0 };
            const std::uint32_t dim371JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   27  ,   55  ,   93  ,   91  ,   49  ,   931 ,   99  ,   1887    ,0 };
            const std::uint32_t dim372JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   13  ,   11  ,   81  ,   175 ,   171 ,   203 ,   679 ,   239 ,0 };
            const std::uint32_t dim373JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   19  ,   35  ,   79  ,   51  ,   163 ,   571 ,   363 ,   3903    ,0 };
            const std::uint32_t dim374JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   3   ,   11  ,   99  ,   57  ,   479 ,   571 ,   487 ,   2141    ,0 };
            const std::uint32_t dim375JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   1   ,   3   ,   123 ,   191 ,   349 ,   523 ,   53  ,   2991    ,0 };
            const std::uint32_t dim376JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   17  ,   1   ,   5   ,   131 ,   279 ,   717 ,   1725    ,   35  ,0 };
            const std::uint32_t dim377JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   9   ,   43  ,   29  ,   9   ,   487 ,   349 ,   457 ,   2551    ,0 };
            const std::uint32_t dim378JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   7   ,   55  ,   75  ,   245 ,   249 ,   623 ,   1681    ,   2345    ,0 };
            const std::uint32_t dim379JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   15  ,   35  ,   111 ,   185 ,   269 ,   913 ,   1899    ,   4059    ,0 };
            const std::uint32_t dim380JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   1   ,   51  ,   43  ,   159 ,   273 ,   329 ,   863 ,   831 ,0 };
            const std::uint32_t dim381JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   31  ,   35  ,   23  ,   135 ,   223 ,   333 ,   1265    ,   1183    ,0 };
            const std::uint32_t dim382JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   9   ,   21  ,   93  ,   33  ,   341 ,   649 ,   1707    ,   1995    ,0 };
            const std::uint32_t dim383JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   9   ,   9   ,   9   ,   175 ,   331 ,   709 ,   927 ,   423 ,0 };
            const std::uint32_t dim384JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   5   ,   41  ,   31  ,   105 ,   223 ,   17  ,   1485    ,   2133    ,0 };
            const std::uint32_t dim385JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   23  ,   7   ,   95  ,   87  ,   303 ,   817 ,   1019    ,   3335    ,0 };
            const std::uint32_t dim386JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   21  ,   3   ,   7   ,   133 ,   23  ,   235 ,   1311    ,   531 ,0 };
            const std::uint32_t dim387JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   25  ,   35  ,   69  ,   251 ,   37  ,   5   ,   1147    ,   2593    ,0 };
            const std::uint32_t dim388JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   21  ,   55  ,   27  ,   129 ,   239 ,   887 ,   1759    ,   3211    ,0 };
            const std::uint32_t dim389JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   3   ,   41  ,   13  ,   141 ,   339 ,   921 ,   1081    ,   4047    ,0 };
            const std::uint32_t dim390JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   1   ,   49  ,   51  ,   91  ,   357 ,   259 ,   547 ,   189 ,0 };
            const std::uint32_t dim391JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   15  ,   29  ,   43  ,   165 ,   213 ,   59  ,   429 ,   1831    ,0 };
            const std::uint32_t dim392JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   25  ,   11  ,   37  ,   67  ,   5   ,   77  ,   915 ,   3865    ,0 };
            const std::uint32_t dim393JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   31  ,   63  ,   61  ,   209 ,   283 ,   223 ,   1253    ,   2137    ,0 };
            const std::uint32_t dim394JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   13  ,   45  ,   65  ,   105 ,   419 ,   909 ,   1943    ,   2201    ,0 };
            const std::uint32_t dim395JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   9   ,   27  ,   21  ,   233 ,   37  ,   23  ,   921 ,   969 ,0 };
            const std::uint32_t dim396JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   31  ,   55  ,   39  ,   127 ,   455 ,   397 ,   65  ,   2381    ,0 };
            const std::uint32_t dim397JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   27  ,   57  ,   39  ,   137 ,   263 ,   519 ,   427 ,   3289    ,0 };
            const std::uint32_t dim398JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   9   ,   29  ,   21  ,   99  ,   21  ,   807 ,   1871    ,   2875    ,0 };
            const std::uint32_t dim399JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   27  ,   59  ,   3   ,   15  ,   189 ,   681 ,   305 ,   2969    ,0 };
            const std::uint32_t dim400JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   25  ,   43  ,   111 ,   179 ,   281 ,   377 ,   1885    ,   815 ,0 };
            const std::uint32_t dim401JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   15  ,   13  ,   17  ,   99  ,   53  ,   269 ,   1199    ,   1771    ,0 };
            const std::uint32_t dim402JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   7   ,   59  ,   115 ,   209 ,   327 ,   913 ,   715 ,   279 ,0 };
            const std::uint32_t dim403JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   11  ,   29  ,   81  ,   69  ,   191 ,   453 ,   379 ,   1379    ,0 };
            const std::uint32_t dim404JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   1   ,   29  ,   85  ,   181 ,   281 ,   463 ,   137 ,   2779    ,0 };
            const std::uint32_t dim405JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   25  ,   39  ,   45  ,   241 ,   87  ,   11  ,   511 ,   1919    ,0 };
            const std::uint32_t dim406JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   21  ,   17  ,   57  ,   249 ,   91  ,   165 ,   1867    ,   615 ,0 };
            const std::uint32_t dim407JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   29  ,   47  ,   79  ,   83  ,   3   ,   765 ,   1803    ,   2741    ,0 };
            const std::uint32_t dim408JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   29  ,   41  ,   23  ,   9   ,   205 ,   657 ,   721 ,   2877    ,0 };
            const std::uint32_t dim409JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   31  ,   21  ,   71  ,   217 ,   19  ,   589 ,   281 ,   719 ,0 };
            const std::uint32_t dim410JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   11  ,   37  ,   3   ,   159 ,   41  ,   823 ,   1519    ,   3395    ,0 };
            const std::uint32_t dim411JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   7   ,   51  ,   49  ,   193 ,   37  ,   981 ,   687 ,   3219    ,0 };
            const std::uint32_t dim412JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   3   ,   27  ,   79  ,   195 ,   155 ,   613 ,   1933    ,   2083    ,0 };
            const std::uint32_t dim413JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   13  ,   39  ,   75  ,   109 ,   395 ,   809 ,   545 ,   499 ,0 };
            const std::uint32_t dim414JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   1   ,   63  ,   47  ,   77  ,   455 ,   617 ,   739 ,   2885    ,0 };
            const std::uint32_t dim415JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   23  ,   59  ,   117 ,   47  ,   379 ,   349 ,   1967    ,   1895    ,0 };
            const std::uint32_t dim416JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   1   ,   3   ,   7   ,   7   ,   105 ,   703 ,   1777    ,   113 ,0 };
            const std::uint32_t dim417JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   7   ,   25  ,   69  ,   123 ,   257 ,   513 ,   41  ,   2689    ,0 };
            const std::uint32_t dim418JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   7   ,   9   ,   11  ,   67  ,   27  ,   283 ,   1139    ,   1961    ,0 };
            const std::uint32_t dim419JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   3   ,   5   ,   53  ,   251 ,   139 ,   913 ,   267 ,   1931    ,0 };
            const std::uint32_t dim420JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   3   ,   11  ,   79  ,   211 ,   27  ,   551 ,   339 ,   3383    ,0 };
            const std::uint32_t dim421JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   9   ,   47  ,   111 ,   47  ,   399 ,   353 ,   1707    ,   603 ,0 };
            const std::uint32_t dim422JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   1   ,   43  ,   17  ,   19  ,   335 ,   713 ,   645 ,   3227    ,0 };
            const std::uint32_t dim423JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   5   ,   27  ,   17  ,   209 ,   363 ,   821 ,   1365    ,   143 ,0 };
            const std::uint32_t dim424JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   29  ,   11  ,   47  ,   253 ,   421 ,   599 ,   465 ,   2413    ,0 };
            const std::uint32_t dim425JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   17  ,   39  ,   5   ,   47  ,   315 ,   645 ,   713 ,   4023    ,0 };
            const std::uint32_t dim426JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   9   ,   3   ,   11  ,   45  ,   9   ,   831 ,   1513    ,   2655    ,0 };
            const std::uint32_t dim427JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   29  ,   55  ,   113 ,   181 ,   281 ,   329 ,   193 ,   2969    ,0 };
            const std::uint32_t dim428JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   9   ,   15  ,   29  ,   77  ,   11  ,   627 ,   1191    ,   3589    ,0 };
            const std::uint32_t dim429JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   27  ,   53  ,   83  ,   13  ,   409 ,   931 ,   1581    ,   371 ,0 };
            const std::uint32_t dim430JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   11  ,   7   ,   89  ,   143 ,   369 ,   519 ,   947 ,   2047    ,0 };
            const std::uint32_t dim431JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   27  ,   59  ,   27  ,   75  ,   199 ,   965 ,   1669    ,   1713    ,0 };
            const std::uint32_t dim432JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   23  ,   63  ,   91  ,   159 ,   193 ,   355 ,   653 ,   2659    ,0 };
            const std::uint32_t dim433JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   23  ,   37  ,   15  ,   73  ,   457 ,   789 ,   1207    ,   2573    ,0 };
            const std::uint32_t dim434JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   13  ,   23  ,   71  ,   171 ,   479 ,   183 ,   1285    ,   1649    ,0 };
            const std::uint32_t dim435JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   19  ,   13  ,   89  ,   5   ,   319 ,   15  ,   857 ,   3175    ,0 };
            const std::uint32_t dim436JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   29  ,   7   ,   1   ,   249 ,   191 ,   237 ,   683 ,   1261    ,0 };
            const std::uint32_t dim437JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   17  ,   53  ,   99  ,   119 ,   35  ,   63  ,   1845    ,   2681    ,0 };
            const std::uint32_t dim438JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   23  ,   53  ,   39  ,   157 ,   323 ,   537 ,   1989    ,   1233    ,0 };
            const std::uint32_t dim439JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   25  ,   19  ,   9   ,   67  ,   315 ,   499 ,   919 ,   2299    ,0 };
            const std::uint32_t dim440JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   21  ,   49  ,   109 ,   185 ,   403 ,   179 ,   1967    ,   1185    ,0 };
            const std::uint32_t dim441JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   27  ,   53  ,   33  ,   203 ,   179 ,   515 ,   1867    ,   1775    ,0 };
            const std::uint32_t dim442JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   19  ,   25  ,   23  ,   77  ,   51  ,   467 ,   143 ,   1585    ,0 };
            const std::uint32_t dim443JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   19  ,   35  ,   41  ,   97  ,   407 ,   319 ,   1175    ,   241 ,0 };
            const std::uint32_t dim444JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   29  ,   51  ,   41  ,   91  ,   223 ,   671 ,   729 ,   2009    ,0 };
            const std::uint32_t dim445JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   7   ,   55  ,   125 ,   75  ,   425 ,   699 ,   1837    ,   1515    ,0 };
            const std::uint32_t dim446JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   27  ,   59  ,   59  ,   235 ,   43  ,   77  ,   1433    ,   3689    ,0 };
            const std::uint32_t dim447JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   19  ,   59  ,   69  ,   85  ,   199 ,   173 ,   1947    ,   1383    ,0 };
            const std::uint32_t dim448JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   29  ,   47  ,   121 ,   131 ,   45  ,   341 ,   85  ,   257 ,0 };
            const std::uint32_t dim449JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   17  ,   17  ,   113 ,   103 ,   407 ,   815 ,   225 ,   2267    ,0 };
            const std::uint32_t dim450JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   23  ,   19  ,   65  ,   173 ,   475 ,   527 ,   271 ,   261 ,0 };
            const std::uint32_t dim451JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   23  ,   51  ,   5   ,   75  ,   403 ,   277 ,   1897    ,   353 ,0 };
            const std::uint32_t dim452JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   31  ,   49  ,   73  ,   93  ,   55  ,   99  ,   403 ,   659 ,0 };
            const std::uint32_t dim453JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   29  ,   17  ,   57  ,   141 ,   209 ,   907 ,   431 ,   2265    ,0 };
            const std::uint32_t dim454JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   25  ,   55  ,   105 ,   61  ,   273 ,   201 ,   23  ,   1211    ,0 };
            const std::uint32_t dim455JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   3   ,   63  ,   41  ,   121 ,   161 ,   713 ,   1885    ,   225 ,0 };
            const std::uint32_t dim456JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   11  ,   53  ,   63  ,   175 ,   439 ,   1   ,   953 ,   481 ,0 };
            const std::uint32_t dim457JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   1   ,   27  ,   65  ,   189 ,   223 ,   659 ,   413 ,   3677    ,0 };
            const std::uint32_t dim458JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   17  ,   9   ,   51  ,   39  ,   307 ,   811 ,   941 ,   2297    ,0 };
            const std::uint32_t dim459JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   1   ,   41  ,   77  ,   237 ,   47  ,   533 ,   1783    ,   1385    ,0 };
            const std::uint32_t dim460JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   19  ,   39  ,   31  ,   249 ,   449 ,   639 ,   1789    ,   3479    ,0 };
            const std::uint32_t dim461JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   9   ,   9   ,   9   ,   19  ,   481 ,   411 ,   1669    ,   863 ,0 };
            const std::uint32_t dim462JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   15  ,   15  ,   89  ,   161 ,   171 ,   377 ,   2031    ,   389 ,0 };
            const std::uint32_t dim463JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   7   ,   49  ,   83  ,   81  ,   181 ,   395 ,   1197    ,   2455    ,0 };
            const std::uint32_t dim464JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   15  ,   25  ,   21  ,   35  ,   287 ,   369 ,   693 ,   1753    ,0 };
            const std::uint32_t dim465JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   5   ,   19  ,   41  ,   241 ,   459 ,   427 ,   631 ,   1109    ,0 };
            const std::uint32_t dim466JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   23  ,   13  ,   115 ,   55  ,   145 ,   933 ,   1985    ,   753 ,0 };
            const std::uint32_t dim467JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   19  ,   15  ,   73  ,   67  ,   335 ,   583 ,   315 ,   1559    ,0 };
            const std::uint32_t dim468JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   23  ,   41  ,   65  ,   155 ,   171 ,   1017    ,   1283    ,   1989    ,0 };
            const std::uint32_t dim469JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   23  ,   53  ,   75  ,   91  ,   253 ,   41  ,   101 ,   1943    ,0 };
            const std::uint32_t dim470JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   25  ,   13  ,   5   ,   71  ,   437 ,   553 ,   701 ,   805 ,0 };
            const std::uint32_t dim471JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   3   ,   3   ,   61  ,   255 ,   409 ,   753 ,   1265    ,   2739    ,0 };
            const std::uint32_t dim472JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   25  ,   33  ,   69  ,   41  ,   367 ,   133 ,   809 ,   1421    ,0 };
            const std::uint32_t dim473JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   3   ,   59  ,   15  ,   229 ,   313 ,   667 ,   45  ,   1485    ,0 };
            const std::uint32_t dim474JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   3   ,   45  ,   73  ,   245 ,   47  ,   489 ,   1715    ,   3167    ,0 };
            const std::uint32_t dim475JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   23  ,   23  ,   107 ,   1   ,   171 ,   993 ,   1617    ,   3665    ,0 };
            const std::uint32_t dim476JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   5   ,   41  ,   9   ,   221 ,   91  ,   611 ,   639 ,   3709    ,0 };
            const std::uint32_t dim477JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   17  ,   31  ,   55  ,   23  ,   75  ,   501 ,   1605    ,   2361    ,0 };
            const std::uint32_t dim478JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   19  ,   27  ,   37  ,   111 ,   393 ,   75  ,   523 ,   2079    ,0 };
            const std::uint32_t dim479JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   13  ,   17  ,   103 ,   177 ,   331 ,   431 ,   419 ,   2781    ,0 };
            const std::uint32_t dim480JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   31  ,   57  ,   9   ,   87  ,   111 ,   761 ,   1259    ,   3645    ,0 };
            const std::uint32_t dim481JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   29  ,   39  ,   117 ,   207 ,   25  ,   263 ,   1875    ,   3325    ,   1773    ,0 };
            const std::uint32_t dim482JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   21  ,   55  ,   105 ,   43  ,   155 ,   933 ,   585 ,   1617    ,   1705    ,0 };
            const std::uint32_t dim483JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   29  ,   37  ,   67  ,   165 ,   229 ,   517 ,   71  ,   3927    ,   1131    ,0 };
            const std::uint32_t dim484JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   1   ,   15  ,   7   ,   139 ,   431 ,   599 ,   101 ,   1167    ,   55  ,0 };
            const std::uint32_t dim485JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   5   ,   31  ,   15  ,   99  ,   375 ,   491 ,   293 ,   2521    ,   1599    ,0 };
            const std::uint32_t dim486JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   29  ,   59  ,   99  ,   155 ,   295 ,   21  ,   1459    ,   2263    ,   1997    ,0 };
            const std::uint32_t dim487JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   29  ,   61  ,   103 ,   151 ,   37  ,   431 ,   1893    ,   2835    ,   6509    ,0 };
            const std::uint32_t dim488JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   17  ,   15  ,   1   ,   163 ,   481 ,   547 ,   701 ,   2957    ,   7071    ,0 };
            const std::uint32_t dim489JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   29  ,   41  ,   51  ,   223 ,   133 ,   49  ,   753 ,   3769    ,   8139    ,0 };
            const std::uint32_t dim490JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   23  ,   23  ,   21  ,   107 ,   9   ,   445 ,   215 ,   857 ,   7913    ,0 };
            const std::uint32_t dim491JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   17  ,   13  ,   11  ,   111 ,   419 ,   433 ,   1289    ,   2855    ,   2157    ,0 };
            const std::uint32_t dim492JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   31  ,   3   ,   97  ,   223 ,   143 ,   117 ,   563 ,   2179    ,   1053    ,0 };
            const std::uint32_t dim493JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   7   ,   25  ,   115 ,   151 ,   181 ,   999 ,   1027    ,   795 ,   679 ,0 };
            const std::uint32_t dim494JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   31  ,   23  ,   85  ,   125 ,   135 ,   1001    ,   909 ,   339 ,   5693    ,0 };
            const std::uint32_t dim495JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   29  ,   17  ,   105 ,   239 ,   467 ,   875 ,   1135    ,   1859    ,   6399    ,0 };
            const std::uint32_t dim496JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   19  ,   59  ,   99  ,   29  ,   177 ,   879 ,   1817    ,   3747    ,   1855    ,0 };
            const std::uint32_t dim497JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   23  ,   5   ,   29  ,   53  ,   111 ,   341 ,   1713    ,   2285    ,   7033    ,0 };
            const std::uint32_t dim498JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   7   ,   55  ,   67  ,   173 ,   273 ,   881 ,   1405    ,   1663    ,   2135    ,0 };
            const std::uint32_t dim499JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   1   ,   39  ,   11  ,   63  ,   107 ,   905 ,   629 ,   1773    ,   1059    ,0 };
            const std::uint32_t dim500JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   29  ,   51  ,   111 ,   189 ,   337 ,   505 ,   453 ,   1549    ,   3697    ,0 };
            const std::uint32_t dim501JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   23  ,   57  ,   21  ,   61  ,   161 ,   695 ,   1097    ,   809 ,   5737    ,0 };
            const std::uint32_t dim502JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   15  ,   55  ,   93  ,   65  ,   101 ,   521 ,   1273    ,   1949    ,   7325    ,0 };
            const std::uint32_t dim503JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   23  ,   31  ,   37  ,   51  ,   205 ,   261 ,   647 ,   1905    ,   4407    ,0 };
            const std::uint32_t dim504JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   3   ,   9   ,   91  ,   51  ,   271 ,   623 ,   1611    ,   563 ,   4687    ,0 };
            const std::uint32_t dim505JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   11  ,   61  ,   95  ,   215 ,   347 ,   171 ,   519 ,   2331    ,   2189    ,0 };
            const std::uint32_t dim506JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   25  ,   13  ,   87  ,   159 ,   87  ,   915 ,   463 ,   1345    ,   5901    ,0 };
            const std::uint32_t dim507JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   31  ,   21  ,   81  ,   75  ,   153 ,   337 ,   2025    ,   233 ,   4999    ,0 };
            const std::uint32_t dim508JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   23  ,   25  ,   81  ,   149 ,   225 ,   799 ,   159 ,   799 ,   687 ,0 };
            const std::uint32_t dim509JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   23  ,   55  ,   67  ,   47  ,   375 ,   657 ,   877 ,   1505    ,   1757    ,0 };
            const std::uint32_t dim510JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   17  ,   7   ,   123 ,   71  ,   203 ,   457 ,   201 ,   9   ,   6671    ,0 };
            const std::uint32_t dim511JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   1   ,   55  ,   7   ,   133 ,   65  ,   891 ,   1705    ,   389 ,   4601    ,0 };
            const std::uint32_t dim512JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   21  ,   59  ,   101 ,   105 ,   241 ,   231 ,   363 ,   4029    ,   1279    ,0 };
            const std::uint32_t dim513JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   31  ,   61  ,   115 ,   219 ,   249 ,   575 ,   201 ,   547 ,   5315    ,0 };
            const std::uint32_t dim514JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   11  ,   3   ,   75  ,   219 ,   183 ,   771 ,   725 ,   2175    ,   4077    ,0 };
            const std::uint32_t dim515JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   1   ,   37  ,   1   ,   165 ,   431 ,   423 ,   2021    ,   475 ,   5151    ,0 };
            const std::uint32_t dim516JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   15  ,   59  ,   25  ,   133 ,   377 ,   747 ,   23  ,   1195    ,   3303    ,0 };
            const std::uint32_t dim517JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   23  ,   63  ,   121 ,   159 ,   403 ,   143 ,   187 ,   1481    ,   4755    ,0 };
            const std::uint32_t dim518JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   21  ,   29  ,   55  ,   165 ,   483 ,   495 ,   579 ,   1197    ,   4841    ,0 };
            const std::uint32_t dim519JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   27  ,   7   ,   111 ,   57  ,   353 ,   1023    ,   1593    ,   1447    ,   5819    ,0 };
            const std::uint32_t dim520JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   13  ,   37  ,   115 ,   65  ,   23  ,   707 ,   603 ,   1805    ,   6011    ,0 };
            const std::uint32_t dim521JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   9   ,   47  ,   87  ,   195 ,   125 ,   515 ,   1885    ,   89  ,   1377    ,0 };
            const std::uint32_t dim522JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   1   ,   25  ,   11  ,   73  ,   183 ,   897 ,   981 ,   275 ,   331 ,0 };
            const std::uint32_t dim523JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   13  ,   53  ,   125 ,   37  ,   145 ,   763 ,   1991    ,   1971    ,   4385    ,0 };
            const std::uint32_t dim524JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   29  ,   53  ,   69  ,   97  ,   415 ,   151 ,   1389    ,   2867    ,   3085    ,0 };
            const std::uint32_t dim525JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   21  ,   51  ,   77  ,   115 ,   81  ,   197 ,   91  ,   3417    ,   2357    ,0 };
            const std::uint32_t dim526JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   31  ,   31  ,   21  ,   21  ,   93  ,   221 ,   1401    ,   3253    ,   6875    ,0 };
            const std::uint32_t dim527JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   11  ,   17  ,   87  ,   75  ,   333 ,   871 ,   1679    ,   2943    ,   4803    ,0 };
            const std::uint32_t dim528JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   11  ,   61  ,   67  ,   141 ,   79  ,   757 ,   965 ,   1999    ,   6363    ,0 };
            const std::uint32_t dim529JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   27  ,   13  ,   109 ,   137 ,   235 ,   1007    ,   1307    ,   341 ,   3957    ,0 };
            const std::uint32_t dim530JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   15  ,   37  ,   47  ,   247 ,   295 ,   867 ,   1433    ,   553 ,   5365    ,0 };
            const std::uint32_t dim531JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   13  ,   29  ,   77  ,   155 ,   423 ,   823 ,   1117    ,   3939    ,   1423    ,0 };
            const std::uint32_t dim532JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   17  ,   27  ,   47  ,   73  ,   79  ,   329 ,   1473    ,   3241    ,   697 ,0 };
            const std::uint32_t dim533JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   23  ,   5   ,   47  ,   89  ,   427 ,   893 ,   2031    ,   3415    ,   6367    ,0 };
            const std::uint32_t dim534JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   17  ,   47  ,   31  ,   113 ,   461 ,   417 ,   2017    ,   41  ,   2417    ,0 };
            const std::uint32_t dim535JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   11  ,   35  ,   119 ,   95  ,   389 ,   31  ,   871 ,   563 ,   7547    ,0 };
            const std::uint32_t dim536JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   3   ,   49  ,   63  ,   237 ,   511 ,   619 ,   589 ,   3571    ,   1883    ,0 };
            const std::uint32_t dim537JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   1   ,   29  ,   17  ,   117 ,   173 ,   399 ,   443 ,   2625    ,   2009    ,0 };
            const std::uint32_t dim538JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   23  ,   47  ,   5   ,   167 ,   413 ,   513 ,   509 ,   853 ,   3509    ,0 };
            const std::uint32_t dim539JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   13  ,   15  ,   33  ,   165 ,   21  ,   163 ,   1613    ,   3387    ,   645 ,0 };
            const std::uint32_t dim540JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   7   ,   33  ,   59  ,   25  ,   65  ,   243 ,   1253    ,   1893    ,   1637    ,0 };
            const std::uint32_t dim541JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   21  ,   63  ,   51  ,   167 ,   131 ,   171 ,   651 ,   295 ,   5775    ,0 };
            const std::uint32_t dim542JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   7   ,   23  ,   31  ,   171 ,   85  ,   859 ,   1691    ,   2757    ,   1351    ,0 };
            const std::uint32_t dim543JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   31  ,   7   ,   25  ,   69  ,   183 ,   417 ,   39  ,   2671    ,   5197    ,0 };
            const std::uint32_t dim544JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   17  ,   21  ,   57  ,   145 ,   23  ,   933 ,   2031    ,   65  ,   4583    ,0 };
            const std::uint32_t dim545JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   1   ,   59  ,   117 ,   191 ,   197 ,   627 ,   659 ,   2873    ,   3865    ,0 };
            const std::uint32_t dim546JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   23  ,   51  ,   45  ,   47  ,   147 ,   779 ,   1619    ,   1017    ,   3769    ,0 };
            const std::uint32_t dim547JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   9   ,   1   ,   75  ,   151 ,   117 ,   483 ,   1499    ,   2143    ,   5873    ,0 };
            const std::uint32_t dim548JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   13  ,   31  ,   105 ,   115 ,   199 ,   111 ,   1403    ,   1833    ,   7923    ,0 };
            const std::uint32_t dim549JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   29  ,   53  ,   121 ,   149 ,   419 ,   107 ,   1299    ,   1925    ,   4409    ,0 };
            const std::uint32_t dim550JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   21  ,   25  ,   63  ,   97  ,   145 ,   71  ,   1693    ,   465 ,   5607    ,0 };
            const std::uint32_t dim551JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   25  ,   43  ,   77  ,   177 ,   53  ,   495 ,   1983    ,   4083    ,   2107    ,0 };
            const std::uint32_t dim552JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   7   ,   51  ,   109 ,   29  ,   171 ,   847 ,   673 ,   2929    ,   3887    ,0 };
            const std::uint32_t dim553JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   31  ,   47  ,   63  ,   225 ,   371 ,   453 ,   1075    ,   2293    ,   3323    ,0 };
            const std::uint32_t dim554JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   31  ,   29  ,   67  ,   227 ,   135 ,   369 ,   481 ,   187 ,   3237    ,0 };
            const std::uint32_t dim555JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   1   ,   29  ,   49  ,   157 ,   99  ,   741 ,   279 ,   1963    ,   7881    ,0 };
            const std::uint32_t dim556JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   17  ,   49  ,   33  ,   73  ,   103 ,   941 ,   209 ,   1329    ,   3   ,0 };
            const std::uint32_t dim557JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   17  ,   41  ,   53  ,   57  ,   163 ,   761 ,   1855    ,   3423    ,   5317    ,0 };
            const std::uint32_t dim558JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   11  ,   13  ,   59  ,   37  ,   351 ,   561 ,   1213    ,   2355    ,   8095    ,0 };
            const std::uint32_t dim559JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   3   ,   31  ,   47  ,   237 ,   101 ,   167 ,   1623    ,   645 ,   4787    ,0 };
            const std::uint32_t dim560JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   21  ,   33  ,   55  ,   15  ,   433 ,   129 ,   279 ,   2131    ,   2943    ,0 };
            const std::uint32_t dim561JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   9   ,   55  ,   71  ,   151 ,   273 ,   901 ,   427 ,   3749    ,   8163    ,0 };
            const std::uint32_t dim562JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   13  ,   63  ,   11  ,   63  ,   477 ,   743 ,   1391    ,   2045    ,   6985    ,0 };
            const std::uint32_t dim563JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   31  ,   25  ,   93  ,   217 ,   39  ,   263 ,   1411    ,   3   ,   7313    ,0 };
            const std::uint32_t dim564JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   21  ,   13  ,   3   ,   255 ,   107 ,   851 ,   1281    ,   959 ,   3955    ,0 };
            const std::uint32_t dim565JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   19  ,   55  ,   53  ,   201 ,   199 ,   361 ,   805 ,   579 ,   1459    ,0 };
            const std::uint32_t dim566JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   9   ,   59  ,   109 ,   245 ,   29  ,   21  ,   137 ,   717 ,   607 ,0 };
            const std::uint32_t dim567JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   15  ,   23  ,   49  ,   3   ,   195 ,   185 ,   85  ,   3885    ,   5859    ,0 };
            const std::uint32_t dim568JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   13  ,   21  ,   7   ,   65  ,   185 ,   541 ,   305 ,   79  ,   3125    ,0 };
            const std::uint32_t dim569JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   7   ,   59  ,   11  ,   125 ,   127 ,   283 ,   943 ,   3545    ,   1617    ,0 };
            const std::uint32_t dim570JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   19  ,   39  ,   73  ,   167 ,   431 ,   147 ,   3   ,   1099    ,   6311    ,0 };
            const std::uint32_t dim571JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   29  ,   57  ,   109 ,   169 ,   49  ,   457 ,   469 ,   3093    ,   7505    ,0 };
            const std::uint32_t dim572JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   15  ,   29  ,   69  ,   133 ,   423 ,   737 ,   673 ,   2529    ,   2065    ,0 };
            const std::uint32_t dim573JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   21  ,   47  ,   15  ,   175 ,   17  ,   419 ,   1917    ,   1183    ,   429 ,0 };
            const std::uint32_t dim574JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   31  ,   43  ,   19  ,   63  ,   395 ,   331 ,   385 ,   3879    ,   3233    ,0 };
            const std::uint32_t dim575JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   5   ,   11  ,   101 ,   65  ,   315 ,   805 ,   719 ,   641 ,   343 ,0 };
            const std::uint32_t dim576JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   15  ,   5   ,   17  ,   115 ,   503 ,   395 ,   531 ,   1201    ,   7225    ,0 };
            const std::uint32_t dim577JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   3   ,   35  ,   29  ,   1   ,   297 ,   421 ,   1365    ,   1491    ,   7973    ,0 };
            const std::uint32_t dim578JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   1   ,   59  ,   79  ,   13  ,   337 ,   717 ,   1229    ,   2587    ,   5659    ,0 };
            const std::uint32_t dim579JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   21  ,   15  ,   27  ,   19  ,   195 ,   27  ,   267 ,   381 ,   1969    ,0 };
            const std::uint32_t dim580JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   25  ,   63  ,   119 ,   155 ,   243 ,   229 ,   897 ,   629 ,   7515    ,0 };
            const std::uint32_t dim581JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   13  ,   37  ,   35  ,   31  ,   485 ,   729 ,   123 ,   1645    ,   457 ,0 };
            const std::uint32_t dim582JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   17  ,   15  ,   47  ,   149 ,   311 ,   189 ,   1925    ,   9   ,   7639    ,0 };
            const std::uint32_t dim583JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   1   ,   1   ,   127 ,   197 ,   109 ,   49  ,   265 ,   3643    ,   3629    ,0 };
            const std::uint32_t dim584JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   21  ,   49  ,   71  ,   187 ,   189 ,   631 ,   1449    ,   775 ,   5973    ,0 };
            const std::uint32_t dim585JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   27  ,   15  ,   17  ,   137 ,   393 ,   807 ,   1189    ,   2731    ,   6337    ,0 };
            const std::uint32_t dim586JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   3   ,   43  ,   3   ,   77  ,   487 ,   539 ,   1781    ,   3261    ,   2775    ,0 };
            const std::uint32_t dim587JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   29  ,   31  ,   83  ,   225 ,   159 ,   971 ,   1899    ,   1035    ,   5383    ,0 };
            const std::uint32_t dim588JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   27  ,   1   ,   15  ,   141 ,   485 ,   639 ,   1895    ,   3129    ,   4489    ,0 };
            const std::uint32_t dim589JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   9   ,   17  ,   21  ,   231 ,   363 ,   637 ,   1851    ,   3675    ,   5371    ,0 };
            const std::uint32_t dim590JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   9   ,   17  ,   91  ,   243 ,   51  ,   565 ,   491 ,   3333    ,   3329    ,0 };
            const std::uint32_t dim591JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   13  ,   9   ,   19  ,   227 ,   353 ,   111 ,   1805    ,   3917    ,   6849    ,0 };
            const std::uint32_t dim592JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   29  ,   31  ,   27  ,   57  ,   421 ,   155 ,   1385    ,   999 ,   1581    ,0 };
            const std::uint32_t dim593JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   1   ,   55  ,   35  ,   35  ,   311 ,   357 ,   1569    ,   2693    ,   2251    ,0 };
            const std::uint32_t dim594JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   27  ,   41  ,   111 ,   119 ,   265 ,   165 ,   1999    ,   2067    ,   7801    ,0 };
            const std::uint32_t dim595JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   31  ,   55  ,   31  ,   39  ,   305 ,   581 ,   373 ,   2523    ,   2153    ,0 };
            const std::uint32_t dim596JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   9   ,   19  ,   115 ,   41  ,   261 ,   209 ,   897 ,   409 ,   5201    ,0 };
            const std::uint32_t dim597JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   3   ,   15  ,   95  ,   143 ,   407 ,   719 ,   1763    ,   1763    ,   1173    ,0 };
            const std::uint32_t dim598JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   17  ,   13  ,   69  ,   17  ,   293 ,   815 ,   1361    ,   259 ,   6751    ,0 };
            const std::uint32_t dim599JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   11  ,   53  ,   13  ,   195 ,   153 ,   445 ,   1873    ,   1159    ,   4739    ,0 };
            const std::uint32_t dim600JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   3   ,   25  ,   57  ,   229 ,   269 ,   299 ,   1687    ,   2707    ,   7049    ,0 };
            const std::uint32_t dim601JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   5   ,   23  ,   89  ,   171 ,   207 ,   523 ,   2031    ,   2513    ,   2475    ,0 };
            const std::uint32_t dim602JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   25  ,   57  ,   125 ,   109 ,   203 ,   671 ,   781 ,   295 ,   4001    ,0 };
            const std::uint32_t dim603JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   17  ,   37  ,   51  ,   169 ,   441 ,   797 ,   871 ,   3267    ,   5695    ,0 };
            const std::uint32_t dim604JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   17  ,   25  ,   97  ,   41  ,   377 ,   643 ,   1463    ,   141 ,   3961    ,0 };
            const std::uint32_t dim605JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   17  ,   35  ,   111 ,   91  ,   253 ,   237 ,   1491    ,   2839    ,   2265    ,0 };
            const std::uint32_t dim606JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   23  ,   7   ,   47  ,   61  ,   263 ,   591 ,   1365    ,   2371    ,   4209    ,0 };
            const std::uint32_t dim607JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   7   ,   51  ,   117 ,   161 ,   383 ,   303 ,   1765    ,   3105    ,   3961    ,0 };
            const std::uint32_t dim608JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   11  ,   55  ,   111 ,   55  ,   417 ,   713 ,   305 ,   1781    ,   5283    ,0 };
            const std::uint32_t dim609JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   25  ,   51  ,   17  ,   215 ,   335 ,   47  ,   1789    ,   2049    ,   5349    ,0 };
            const std::uint32_t dim610JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   1   ,   9   ,   71  ,   105 ,   397 ,   517 ,   1093    ,   765 ,   5301    ,0 };
            const std::uint32_t dim611JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   31  ,   41  ,   95  ,   153 ,   383 ,   91  ,   1649    ,   3059    ,   6135    ,0 };
            const std::uint32_t dim612JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   19  ,   51  ,   67  ,   119 ,   507 ,   179 ,   571 ,   2767    ,   5517    ,0 };
            const std::uint32_t dim613JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   13  ,   19  ,   35  ,   249 ,   39  ,   425 ,   233 ,   1635    ,   5915    ,0 };
            const std::uint32_t dim614JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   17  ,   15  ,   43  ,   29  ,   351 ,   25  ,   1879    ,   3941    ,   189 ,0 };
            const std::uint32_t dim615JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   13  ,   55  ,   9   ,   7   ,   91  ,   951 ,   1681    ,   2723    ,   4349    ,0 };
            const std::uint32_t dim616JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   27  ,   31  ,   49  ,   33  ,   287 ,   629 ,   851 ,   1353    ,   6391    ,0 };
            const std::uint32_t dim617JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   19  ,   27  ,   45  ,   209 ,   257 ,   141 ,   1771    ,   931 ,   7839    ,0 };
            const std::uint32_t dim618JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   9   ,   47  ,   87  ,   71  ,   183 ,   249 ,   311 ,   1989    ,   1753    ,0 };
            const std::uint32_t dim619JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   7   ,   35  ,   45  ,   199 ,   207 ,   203 ,   831 ,   2643    ,   1155    ,0 };
            const std::uint32_t dim620JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   5   ,   11  ,   27  ,   187 ,   405 ,   747 ,   261 ,   1279    ,   6153    ,0 };
            const std::uint32_t dim621JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   7   ,   43  ,   23  ,   117 ,   421 ,   775 ,   1657    ,   1071    ,   4551    ,0 };
            const std::uint32_t dim622JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   1   ,   51  ,   5   ,   27  ,   121 ,   459 ,   1251    ,   901 ,   2301    ,0 };
            const std::uint32_t dim623JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   15  ,   47  ,   107 ,   93  ,   79  ,   719 ,   571 ,   65  ,   7589    ,0 };
            const std::uint32_t dim624JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   19  ,   33  ,   103 ,   253 ,   469 ,   109 ,   913 ,   2251    ,   4737    ,0 };
            const std::uint32_t dim625JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   23  ,   29  ,   89  ,   79  ,   253 ,   513 ,   723 ,   3823    ,   5769    ,0 };
            const std::uint32_t dim626JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   27  ,   3   ,   103 ,   171 ,   353 ,   673 ,   1147    ,   529 ,   4737    ,0 };
            const std::uint32_t dim627JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   27  ,   5   ,   103 ,   61  ,   101 ,   759 ,   443 ,   2003    ,   5537    ,0 };
            const std::uint32_t dim628JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   11  ,   15  ,   109 ,   119 ,   473 ,   585 ,   1759    ,   319 ,   5461    ,0 };
            const std::uint32_t dim629JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   19  ,   61  ,   5   ,   255 ,   171 ,   843 ,   823 ,   2713    ,   5313    ,0 };
            const std::uint32_t dim630JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   9   ,   11  ,   57  ,   3   ,   365 ,   471 ,   1179    ,   1999    ,   3333    ,0 };
            const std::uint32_t dim631JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   1   ,   3   ,   3   ,   195 ,   441 ,   193 ,   1905    ,   1753    ,   1839    ,0 };
            const std::uint32_t dim632JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   1   ,   49  ,   99  ,   85  ,   175 ,   603 ,   1569    ,   2201    ,   1979    ,0 };
            const std::uint32_t dim633JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   27  ,   37  ,   61  ,   137 ,   219 ,   469 ,   973 ,   1979    ,   1135    ,0 };
            const std::uint32_t dim634JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   3   ,   59  ,   11  ,   203 ,   415 ,   513 ,   1469    ,   1655    ,   5913    ,0 };
            const std::uint32_t dim635JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   21  ,   23  ,   87  ,   83  ,   21  ,   351 ,   899 ,   1633    ,   6589    ,0 };
            const std::uint32_t dim636JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   5   ,   63  ,   45  ,   201 ,   193 ,   27  ,   1365    ,   1197    ,   1729    ,0 };
            const std::uint32_t dim637JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   1   ,   35  ,   59  ,   157 ,   295 ,   359 ,   383 ,   3191    ,   7019    ,0 };
            const std::uint32_t dim638JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   3   ,   23  ,   17  ,   149 ,   59  ,   115 ,   1101    ,   1879    ,   4243    ,0 };
            const std::uint32_t dim639JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   3   ,   21  ,   71  ,   31  ,   85  ,   93  ,   1691    ,   379 ,   7901    ,0 };
            const std::uint32_t dim640JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   15  ,   7   ,   29  ,   59  ,   191 ,   817 ,   439 ,   453 ,   5073    ,0 };
            const std::uint32_t dim641JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   29  ,   7   ,   119 ,   35  ,   393 ,   9   ,   509 ,   3907    ,   7031    ,0 };
            const std::uint32_t dim642JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   29  ,   51  ,   19  ,   127 ,   399 ,   309 ,   117 ,   3491    ,   5417    ,0 };
            const std::uint32_t dim643JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   31  ,   33  ,   17  ,   119 ,   365 ,   301 ,   527 ,   3341    ,   779 ,0 };
            const std::uint32_t dim644JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   29  ,   41  ,   43  ,   85  ,   133 ,   191 ,   229 ,   3407    ,   3147    ,0 };
            const std::uint32_t dim645JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   7   ,   9   ,   49  ,   121 ,   193 ,   569 ,   467 ,   999 ,   6813    ,0 };
            const std::uint32_t dim646JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   7   ,   23  ,   121 ,   43  ,   173 ,   761 ,   525 ,   3221    ,   5435    ,0 };
            const std::uint32_t dim647JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   15  ,   43  ,   47  ,   149 ,   227 ,   357 ,   1219    ,   4087    ,   1215    ,0 };
            const std::uint32_t dim648JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   1   ,   33  ,   81  ,   195 ,   201 ,   307 ,   1081    ,   3201    ,   4293    ,0 };
            const std::uint32_t dim649JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   11  ,   1   ,   125 ,   119 ,   105 ,   783 ,   117 ,   3465    ,   5713    ,0 };
            const std::uint32_t dim650JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   1   ,   51  ,   17  ,   141 ,   107 ,   875 ,   1135    ,   1213    ,   7113    ,0 };
            const std::uint32_t dim651JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   7   ,   41  ,   63  ,   91  ,   465 ,   893 ,   1663    ,   2717    ,   6313    ,0 };
            const std::uint32_t dim652JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   23  ,   43  ,   77  ,   49  ,   131 ,   953 ,   1591    ,   869 ,   3779    ,0 };
            const std::uint32_t dim653JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   5   ,   9   ,   41  ,   183 ,   403 ,   775 ,   1163    ,   2963    ,   861 ,0 };
            const std::uint32_t dim654JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   27  ,   19  ,   51  ,   139 ,   87  ,   315 ,   831 ,   2587    ,   4847    ,0 };
            const std::uint32_t dim655JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   23  ,   23  ,   117 ,   189 ,   405 ,   735 ,   681 ,   457 ,   337 ,0 };
            const std::uint32_t dim656JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   13  ,   21  ,   25  ,   207 ,   179 ,   715 ,   629 ,   593 ,   6351    ,0 };
            const std::uint32_t dim657JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   25  ,   13  ,   31  ,   245 ,   147 ,   953 ,   1061    ,   3749    ,   6927    ,0 };
            const std::uint32_t dim658JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   29  ,   27  ,   57  ,   5   ,   345 ,   471 ,   599 ,   3677    ,   1801    ,0 };
            const std::uint32_t dim659JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   21  ,   47  ,   27  ,   21  ,   473 ,   881 ,   1973    ,   995 ,   6513    ,0 };
            const std::uint32_t dim660JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   23  ,   1   ,   19  ,   197 ,   43  ,   955 ,   1503    ,   2825    ,   7241    ,0 };
            const std::uint32_t dim661JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   5   ,   51  ,   51  ,   33  ,   349 ,   835 ,   1367    ,   1913    ,   1963    ,0 };
            const std::uint32_t dim662JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   19  ,   63  ,   9   ,   145 ,   335 ,   843 ,   655 ,   1049    ,   3421    ,0 };
            const std::uint32_t dim663JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   1   ,   33  ,   1   ,   9   ,   35  ,   833 ,   629 ,   3453    ,   6341    ,0 };
            const std::uint32_t dim664JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   3   ,   55  ,   119 ,   87  ,   441 ,   43  ,   169 ,   761 ,   753 ,0 };
            const std::uint32_t dim665JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   17  ,   11  ,   87  ,   165 ,   421 ,   1005    ,   1227    ,   3381    ,   1005    ,0 };
            const std::uint32_t dim666JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   17  ,   19  ,   63  ,   71  ,   251 ,   355 ,   1127    ,   2575    ,   1193    ,0 };
            const std::uint32_t dim667JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   9   ,   23  ,   71  ,   173 ,   421 ,   179 ,   1899    ,   2507    ,   8083    ,0 };
            const std::uint32_t dim668JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   1   ,   13  ,   81  ,   169 ,   85  ,   957 ,   1109    ,   2767    ,   447 ,0 };
            const std::uint32_t dim669JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   19  ,   41  ,   61  ,   247 ,   325 ,   273 ,   469 ,   1859    ,   6869    ,0 };
            const std::uint32_t dim670JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   15  ,   3   ,   3   ,   119 ,   377 ,   579 ,   1155    ,   325 ,   143 ,0 };
            const std::uint32_t dim671JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   31  ,   1   ,   43  ,   135 ,   375 ,   383 ,   1497    ,   2759    ,   43  ,0 };
            const std::uint32_t dim672JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   1   ,   63  ,   75  ,   179 ,   447 ,   113 ,   1037    ,   631 ,   4969    ,0 };
            const std::uint32_t dim673JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   13  ,   61  ,   63  ,   229 ,   85  ,   223 ,   153 ,   3987    ,   4685    ,0 };
            const std::uint32_t dim674JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   17  ,   33  ,   17  ,   247 ,   399 ,   559 ,   369 ,   1525    ,   4923    ,0 };
            const std::uint32_t dim675JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   1   ,   63  ,   69  ,   167 ,   407 ,   191 ,   499 ,   1697    ,   3267    ,0 };
            const std::uint32_t dim676JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   31  ,   15  ,   97  ,   183 ,   165 ,   271 ,   1465    ,   931 ,   4061    ,0 };
            const std::uint32_t dim677JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   31  ,   7   ,   121 ,   37  ,   429 ,   375 ,   1539    ,   1383    ,   7317    ,0 };
            const std::uint32_t dim678JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   13  ,   41  ,   49  ,   205 ,   233 ,   847 ,   187 ,   359 ,   2341    ,0 };
            const std::uint32_t dim679JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   25  ,   5   ,   57  ,   119 ,   79  ,   131 ,   1707    ,   1601    ,   1657    ,0 };
            const std::uint32_t dim680JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   21  ,   11  ,   89  ,   149 ,   369 ,   401 ,   623 ,   3001    ,   85  ,0 };
            const std::uint32_t dim681JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   31  ,   9   ,   109 ,   33  ,   31  ,   93  ,   2035    ,   3785    ,   5893    ,0 };
            const std::uint32_t dim682JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   31  ,   57  ,   15  ,   161 ,   333 ,   559 ,   1487    ,   1037    ,   1055    ,0 };
            const std::uint32_t dim683JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   7   ,   9   ,   7   ,   109 ,   151 ,   629 ,   295 ,   105 ,   1121    ,0 };
            const std::uint32_t dim684JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   7   ,   25  ,   49  ,   5   ,   95  ,   321 ,   303 ,   2571    ,   6967    ,0 };
            const std::uint32_t dim685JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   27  ,   13  ,   65  ,   27  ,   507 ,   847 ,   155 ,   3183    ,   5985    ,0 };
            const std::uint32_t dim686JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   17  ,   29  ,   69  ,   23  ,   181 ,   855 ,   1659    ,   889 ,   1273    ,0 };
            const std::uint32_t dim687JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   19  ,   41  ,   109 ,   97  ,   373 ,   591 ,   1715    ,   3927    ,   3101    ,0 };
            const std::uint32_t dim688JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   9   ,   9   ,   75  ,   63  ,   1   ,   39  ,   941 ,   3677    ,   7253    ,0 };
            const std::uint32_t dim689JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   27  ,   37  ,   25  ,   33  ,   213 ,   917 ,   2037    ,   145 ,   4395    ,0 };
            const std::uint32_t dim690JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   23  ,   21  ,   15  ,   195 ,   87  ,   699 ,   1475    ,   429 ,   1641    ,0 };
            const std::uint32_t dim691JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   1   ,   51  ,   117 ,   13  ,   369 ,   711 ,   625 ,   3171    ,   1867    ,0 };
            const std::uint32_t dim692JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   23  ,   11  ,   47  ,   177 ,   511 ,   709 ,   255 ,   2355    ,   71  ,0 };
            const std::uint32_t dim693JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   7   ,   21  ,   21  ,   35  ,   303 ,   105 ,   525 ,   589 ,   5449    ,0 };
            const std::uint32_t dim694JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   21  ,   27  ,   71  ,   177 ,   205 ,   143 ,   385 ,   2949    ,   8169    ,0 };
            const std::uint32_t dim695JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   19  ,   39  ,   79  ,   241 ,   103 ,   489 ,   1399    ,   2781    ,   5533    ,0 };
            const std::uint32_t dim696JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   23  ,   9   ,   121 ,   51  ,   145 ,   927 ,   1457    ,   1891    ,   7475    ,0 };
            const std::uint32_t dim697JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   7   ,   23  ,   67  ,   145 ,   161 ,   63  ,   569 ,   395 ,   6719    ,0 };
            const std::uint32_t dim698JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   5   ,   31  ,   13  ,   9   ,   135 ,   367 ,   1591    ,   1963    ,   7249    ,0 };
            const std::uint32_t dim699JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   7   ,   47  ,   119 ,   195 ,   439 ,   619 ,   551 ,   1955    ,   6913    ,0 };
            const std::uint32_t dim700JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   29  ,   57  ,   43  ,   213 ,   113 ,   339 ,   1943    ,   183 ,   3063    ,0 };
            const std::uint32_t dim701JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   1   ,   3   ,   57  ,   149 ,   495 ,   547 ,   603 ,   907 ,   1349    ,0 };
            const std::uint32_t dim702JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   7   ,   31  ,   87  ,   49  ,   239 ,   827 ,   1451    ,   3171    ,   287 ,0 };
            const std::uint32_t dim703JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   11  ,   41  ,   29  ,   233 ,   101 ,   573 ,   737 ,   3813    ,   7739    ,0 };
            const std::uint32_t dim704JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   19  ,   13  ,   57  ,   177 ,   259 ,   595 ,   263 ,   2851    ,   5771    ,0 };
            const std::uint32_t dim705JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   13  ,   5   ,   27  ,   133 ,   17  ,   725 ,   417 ,   2277    ,   5649    ,0 };
            const std::uint32_t dim706JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   25  ,   57  ,   35  ,   229 ,   253 ,   761 ,   275 ,   2519    ,   7061    ,0 };
            const std::uint32_t dim707JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   9   ,   31  ,   61  ,   181 ,   129 ,   259 ,   1569    ,   817 ,   4665    ,0 };
            const std::uint32_t dim708JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   23  ,   3   ,   69  ,   161 ,   429 ,   143 ,   455 ,   905 ,   3337    ,0 };
            const std::uint32_t dim709JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   21  ,   33  ,   81  ,   187 ,   481 ,   481 ,   1947    ,   3563    ,   4797    ,0 };
            const std::uint32_t dim710JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   15  ,   35  ,   23  ,   187 ,   455 ,   535 ,   85  ,   1067    ,   1793    ,0 };
            const std::uint32_t dim711JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   11  ,   17  ,   89  ,   255 ,   443 ,   791 ,   1617    ,   2979    ,   1357    ,0 };
            const std::uint32_t dim712JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   17  ,   49  ,   1   ,   233 ,   3   ,   587 ,   1203    ,   3185    ,   1173    ,0 };
            const std::uint32_t dim713JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   5   ,   53  ,   37  ,   13  ,   47  ,   1011    ,   1589    ,   1073    ,   5445    ,0 };
            const std::uint32_t dim714JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   15  ,   43  ,   85  ,   167 ,   347 ,   935 ,   1681    ,   261 ,   3623    ,0 };
            const std::uint32_t dim715JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   3   ,   31  ,   121 ,   241 ,   129 ,   555 ,   1737    ,   3557    ,   6515    ,0 };
            const std::uint32_t dim716JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   25  ,   7   ,   125 ,   105 ,   13  ,   927 ,   1929    ,   3869    ,   7429    ,0 };
            const std::uint32_t dim717JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   31  ,   47  ,   3   ,   29  ,   149 ,   827 ,   771 ,   2113    ,   1607    ,0 };
            const std::uint32_t dim718JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   17  ,   17  ,   65  ,   247 ,   109 ,   613 ,   1975    ,   2393    ,   6057    ,0 };
            const std::uint32_t dim719JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   9   ,   43  ,   41  ,   119 ,   335 ,   533 ,   1053    ,   1343    ,   6529    ,0 };
            const std::uint32_t dim720JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   31  ,   59  ,   85  ,   247 ,   485 ,   811 ,   749 ,   89  ,   6677    ,0 };
            const std::uint32_t dim721JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   7   ,   47  ,   77  ,   193 ,   25  ,   27  ,   639 ,   109 ,   6455    ,0 };
            const std::uint32_t dim722JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   15  ,   63  ,   17  ,   81  ,   425 ,   403 ,   1537    ,   3205    ,   6237    ,0 };
            const std::uint32_t dim723JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   21  ,   29  ,   105 ,   135 ,   407 ,   119 ,   793 ,   559 ,   973 ,0 };
            const std::uint32_t dim724JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   1   ,   31  ,   45  ,   97  ,   511 ,   463 ,   1923    ,   2487    ,   1311    ,0 };
            const std::uint32_t dim725JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   13  ,   53  ,   91  ,   149 ,   441 ,   841 ,   1121    ,   3305    ,   975 ,0 };
            const std::uint32_t dim726JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   5   ,   55  ,   81  ,   181 ,   333 ,   63  ,   1157    ,   2831    ,   6231    ,0 };
            const std::uint32_t dim727JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   29  ,   21  ,   69  ,   87  ,   41  ,   623 ,   475 ,   723 ,   5693    ,0 };
            const std::uint32_t dim728JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   23  ,   19  ,   15  ,   25  ,   269 ,   79  ,   1699    ,   691 ,   525 ,0 };
            const std::uint32_t dim729JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   29  ,   23  ,   85  ,   5   ,   431 ,   649 ,   1187    ,   3503    ,   105 ,0 };
            const std::uint32_t dim730JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   27  ,   59  ,   1   ,   81  ,   351 ,   383 ,   1167    ,   3747    ,   5935    ,0 };
            const std::uint32_t dim731JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   21  ,   49  ,   93  ,   5   ,   471 ,   231 ,   1469    ,   1089    ,   5059    ,0 };
            const std::uint32_t dim732JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   31  ,   61  ,   117 ,   161 ,   307 ,   621 ,   1713    ,   1325    ,   283 ,0 };
            const std::uint32_t dim733JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   21  ,   35  ,   7   ,   79  ,   157 ,   723 ,   57  ,   25  ,   2789    ,0 };
            const std::uint32_t dim734JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   9   ,   47  ,   97  ,   1   ,   257 ,   941 ,   553 ,   3811    ,   3775    ,0 };
            const std::uint32_t dim735JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   19  ,   5   ,   73  ,   233 ,   289 ,   241 ,   175 ,   2831    ,   4613    ,0 };
            const std::uint32_t dim736JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   11  ,   61  ,   1   ,   245 ,   223 ,   641 ,   77  ,   1811    ,   3459    ,0 };
            const std::uint32_t dim737JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   21  ,   41  ,   9   ,   175 ,   377 ,   331 ,   1615    ,   325 ,   5413    ,0 };
            const std::uint32_t dim738JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   23  ,   57  ,   99  ,   161 ,   127 ,   47  ,   1923    ,   165 ,   2123    ,0 };
            const std::uint32_t dim739JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   11  ,   15  ,   77  ,   15  ,   323 ,   919 ,   1001    ,   377 ,   6095    ,0 };
            const std::uint32_t dim740JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   25  ,   47  ,   5   ,   25  ,   197 ,   811 ,   179 ,   215 ,   5393    ,0 };
            const std::uint32_t dim741JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   29  ,   37  ,   7   ,   125 ,   3   ,   7   ,   1881    ,   3823    ,   2117    ,0 };
            const std::uint32_t dim742JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   9   ,   61  ,   97  ,   233 ,   233 ,   603 ,   511 ,   17  ,   2081    ,0 };
            const std::uint32_t dim743JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   15  ,   35  ,   73  ,   199 ,   113 ,   575 ,   537 ,   883 ,   6897    ,0 };
            const std::uint32_t dim744JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   17  ,   63  ,   7   ,   181 ,   261 ,   719 ,   591 ,   2575    ,   1065    ,0 };
            const std::uint32_t dim745JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   13  ,   15  ,   1   ,   207 ,   385 ,   277 ,   547 ,   1069    ,   6421    ,0 };
            const std::uint32_t dim746JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   5   ,   3   ,   43  ,   213 ,   509 ,   969 ,   1799    ,   3519    ,   7759    ,0 };
            const std::uint32_t dim747JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   29  ,   51  ,   87  ,   63  ,   257 ,   1001    ,   741 ,   1747    ,   975 ,0 };
            const std::uint32_t dim748JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   5   ,   27  ,   7   ,   27  ,   493 ,   817 ,   319 ,   1435    ,   3243    ,0 };
            const std::uint32_t dim749JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   5   ,   9   ,   113 ,   153 ,   397 ,   63  ,   2037    ,   3319    ,   6355    ,0 };
            const std::uint32_t dim750JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   29  ,   9   ,   97  ,   171 ,   113 ,   729 ,   1939    ,   2741    ,   4699    ,0 };
            const std::uint32_t dim751JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   29  ,   3   ,   49  ,   183 ,   69  ,   313 ,   153 ,   2757    ,   3353    ,0 };
            const std::uint32_t dim752JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   5   ,   39  ,   65  ,   65  ,   405 ,   301 ,   849 ,   1211    ,   3627    ,0 };
            const std::uint32_t dim753JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   19  ,   11  ,   81  ,   181 ,   471 ,   669 ,   139 ,   4019    ,   4057    ,0 };
            const std::uint32_t dim754JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   3   ,   31  ,   125 ,   229 ,   181 ,   913 ,   2035    ,   2081    ,   6573    ,0 };
            const std::uint32_t dim755JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   13  ,   25  ,   37  ,   209 ,   255 ,   761 ,   1485    ,   2833    ,   6617    ,0 };
            const std::uint32_t dim756JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   29  ,   17  ,   55  ,   59  ,   337 ,   953 ,   775 ,   3865    ,   5671    ,0 };
            const std::uint32_t dim757JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   15  ,   37  ,   109 ,   93  ,   303 ,   57  ,   1727    ,   615 ,   3337    ,0 };
            const std::uint32_t dim758JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   31  ,   57  ,   119 ,   57  ,   295 ,   707 ,   1409    ,   3769    ,   6359    ,0 };
            const std::uint32_t dim759JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   31  ,   25  ,   35  ,   191 ,   27  ,   463 ,   875 ,   129 ,   3829    ,0 };
            const std::uint32_t dim760JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   19  ,   29  ,   95  ,   227 ,   487 ,   519 ,   289 ,   965 ,   2121    ,0 };
            const std::uint32_t dim761JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   21  ,   37  ,   7   ,   43  ,   213 ,   673 ,   25  ,   1911    ,   7229    ,0 };
            const std::uint32_t dim762JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   9   ,   55  ,   115 ,   155 ,   119 ,   49  ,   653 ,   3425    ,   299 ,0 };
            const std::uint32_t dim763JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   7   ,   55  ,   65  ,   21  ,   93  ,   295 ,   1097    ,   145 ,   3401    ,0 };
            const std::uint32_t dim764JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   1   ,   19  ,   109 ,   247 ,   499 ,   391 ,   309 ,   59  ,   695 ,0 };
            const std::uint32_t dim765JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   5   ,   9   ,   37  ,   113 ,   233 ,   57  ,   955 ,   437 ,   775 ,   2673    ,0 };
            const std::uint32_t dim766JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   5   ,   27  ,   57  ,   53  ,   149 ,   929 ,   41  ,   1473    ,   4751    ,0 };
            const std::uint32_t dim767JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   5   ,   3   ,   107 ,   57  ,   3   ,   727 ,   2001    ,   3463    ,   4753    ,0 };
            const std::uint32_t dim768JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   3   ,   37  ,   111 ,   97  ,   225 ,   809 ,   135 ,   2049    ,   2373    ,0 };
            const std::uint32_t dim769JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   3   ,   37  ,   57  ,   153 ,   175 ,   851 ,   137 ,   495 ,   4423    ,0 };
            const std::uint32_t dim770JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   25  ,   31  ,   53  ,   51  ,   421 ,   33  ,   1241    ,   2157    ,   867 ,0 };
            const std::uint32_t dim771JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   3   ,   33  ,   15  ,   77  ,   73  ,   51  ,   1131    ,   3387    ,   7935    ,0 };
            const std::uint32_t dim772JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   11  ,   25  ,   27  ,   235 ,   341 ,   133 ,   261 ,   2087    ,   4079    ,0 };
            const std::uint32_t dim773JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   11  ,   63  ,   33  ,   99  ,   65  ,   485 ,   561 ,   2269    ,   8143    ,0 };
            const std::uint32_t dim774JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   13  ,   25  ,   53  ,   65  ,   59  ,   861 ,   1705    ,   627 ,   1097    ,0 };
            const std::uint32_t dim775JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   25  ,   15  ,   67  ,   187 ,   161 ,   747 ,   947 ,   4029    ,   7547    ,0 };
            const std::uint32_t dim776JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   7   ,   27  ,   119 ,   239 ,   197 ,   165 ,   457 ,   1927    ,   6195    ,0 };
            const std::uint32_t dim777JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   27  ,   21  ,   23  ,   93  ,   319 ,   551 ,   1317    ,   69  ,   6735    ,0 };
            const std::uint32_t dim778JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   11  ,   25  ,   45  ,   23  ,   127 ,   327 ,   949 ,   1451    ,   2245    ,   6705    ,0 };
            const std::uint32_t dim779JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   19  ,   23  ,   69  ,   113 ,   53  ,   215 ,   1505    ,   1255    ,   5063    ,0 };
            const std::uint32_t dim780JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   7   ,   19  ,   39  ,   135 ,   437 ,   251 ,   1947    ,   2219    ,   4015    ,0 };
            const std::uint32_t dim781JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   23  ,   39  ,   91  ,   111 ,   395 ,   545 ,   179 ,   937 ,   2531    ,0 };
            const std::uint32_t dim782JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   1   ,   53  ,   113 ,   137 ,   131 ,   461 ,   151 ,   1617    ,   6399    ,0 };
            const std::uint32_t dim783JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   13  ,   3   ,   75  ,   31  ,   175 ,   773 ,   1293    ,   625 ,   6563    ,0 };
            const std::uint32_t dim784JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   9   ,   51  ,   87  ,   223 ,   405 ,   751 ,   1053    ,   1431    ,   4701    ,0 };
            const std::uint32_t dim785JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   21  ,   21  ,   111 ,   145 ,   311 ,   733 ,   635 ,   1369    ,   297 ,0 };
            const std::uint32_t dim786JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   25  ,   5   ,   23  ,   201 ,   179 ,   593 ,   1531    ,   1197    ,   3525    ,0 };
            const std::uint32_t dim787JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   7   ,   17  ,   19  ,   247 ,   401 ,   15  ,   93  ,   245 ,   5987    ,0 };
            const std::uint32_t dim788JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   7   ,   45  ,   119 ,   99  ,   197 ,   163 ,   637 ,   3143    ,   1775    ,0 };
            const std::uint32_t dim789JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   17  ,   7   ,   35  ,   121 ,   155 ,   925 ,   1001    ,   2941    ,   107 ,0 };
            const std::uint32_t dim790JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   15  ,   3   ,   89  ,   205 ,   171 ,   279 ,   763 ,   2343    ,   7825    ,0 };
            const std::uint32_t dim791JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   15  ,   3   ,   113 ,   135 ,   159 ,   217 ,   139 ,   167 ,   589 ,0 };
            const std::uint32_t dim792JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   31  ,   59  ,   89  ,   3   ,   261 ,   953 ,   1527    ,   447 ,   1211    ,0 };
            const std::uint32_t dim793JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   31  ,   39  ,   93  ,   171 ,   497 ,   657 ,   809 ,   2905    ,   2399    ,0 };
            const std::uint32_t dim794JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   27  ,   19  ,   25  ,   179 ,   293 ,   829 ,   1197    ,   3077    ,   6631    ,0 };
            const std::uint32_t dim795JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   31  ,   55  ,   53  ,   177 ,   157 ,   619 ,   197 ,   3675    ,   4691    ,0 };
            const std::uint32_t dim796JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   7   ,   33  ,   85  ,   59  ,   435 ,   653 ,   1363    ,   731 ,   3923    ,0 };
            const std::uint32_t dim797JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   15  ,   35  ,   15  ,   217 ,   333 ,   717 ,   143 ,   4071    ,   4769    ,0 };
            const std::uint32_t dim798JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   23  ,   31  ,   65  ,   77  ,   261 ,   389 ,   1733    ,   4077    ,   3387    ,0 };
            const std::uint32_t dim799JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   21  ,   45  ,   21  ,   103 ,   163 ,   237 ,   1447    ,   141 ,   3995    ,0 };
            const std::uint32_t dim800JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   27  ,   35  ,   61  ,   149 ,   359 ,   131 ,   1309    ,   3283    ,   5905    ,0 };
            const std::uint32_t dim801JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   15  ,   9   ,   15  ,   99  ,   43  ,   115 ,   871 ,   419 ,   2787    ,   7741    ,0 };
            const std::uint32_t dim802JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   1   ,   45  ,   31  ,   87  ,   165 ,   103 ,   2041    ,   1529    ,   5721    ,0 };
            const std::uint32_t dim803JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   3   ,   11  ,   107 ,   9   ,   367 ,   401 ,   1571    ,   2657    ,   4745    ,0 };
            const std::uint32_t dim804JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   31  ,   51  ,   35  ,   53  ,   131 ,   441 ,   1421    ,   2367    ,   7713    ,0 };
            const std::uint32_t dim805JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   21  ,   49  ,   109 ,   117 ,   263 ,   827 ,   1975    ,   2639    ,   1249    ,0 };
            const std::uint32_t dim806JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   7   ,   3   ,   87  ,   185 ,   493 ,   721 ,   1363    ,   2201    ,   1067    ,0 };
            const std::uint32_t dim807JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   13  ,   41  ,   113 ,   105 ,   111 ,   65  ,   705 ,   4079    ,   2461    ,0 };
            const std::uint32_t dim808JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   9   ,   1   ,   75  ,   103 ,   181 ,   587 ,   1531    ,   461 ,   6551    ,0 };
            const std::uint32_t dim809JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   13  ,   43  ,   19  ,   131 ,   233 ,   209 ,   175 ,   625 ,   985 ,0 };
            const std::uint32_t dim810JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   23  ,   1   ,   87  ,   233 ,   355 ,   765 ,   869 ,   2569    ,   5919    ,0 };
            const std::uint32_t dim811JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   13  ,   27  ,   41  ,   127 ,   105 ,   299 ,   189 ,   3801    ,   4677    ,0 };
            const std::uint32_t dim812JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   21  ,   49  ,   111 ,   95  ,   27  ,   433 ,   1715    ,   1167    ,   4943    ,0 };
            const std::uint32_t dim813JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   5   ,   17  ,   93  ,   91  ,   79  ,   355 ,   111 ,   1159    ,   4629    ,0 };
            const std::uint32_t dim814JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   29  ,   43  ,   107 ,   91  ,   111 ,   813 ,   537 ,   97  ,   5337    ,0 };
            const std::uint32_t dim815JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   27  ,   1   ,   69  ,   181 ,   247 ,   51  ,   409 ,   1965    ,   4709    ,0 };
            const std::uint32_t dim816JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   7   ,   53  ,   119 ,   109 ,   331 ,   189 ,   761 ,   385 ,   5227    ,0 };
            const std::uint32_t dim817JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   5   ,   61  ,   57  ,   3   ,   157 ,   737 ,   1605    ,   3701    ,   1069    ,0 };
            const std::uint32_t dim818JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   17  ,   27  ,   89  ,   235 ,   53  ,   521 ,   1975    ,   1383    ,   467 ,0 };
            const std::uint32_t dim819JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   25  ,   25  ,   39  ,   149 ,   157 ,   385 ,   1651    ,   105 ,   1487    ,0 };
            const std::uint32_t dim820JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   15  ,   43  ,   37  ,   167 ,   303 ,   655 ,   331 ,   1595    ,   5405    ,0 };
            const std::uint32_t dim821JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   13  ,   29  ,   13  ,   163 ,   405 ,   903 ,   1277    ,   985 ,   1479    ,0 };
            const std::uint32_t dim822JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   1   ,   7   ,   61  ,   9   ,   163 ,   67  ,   209 ,   1923    ,   6587    ,0 };
            const std::uint32_t dim823JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   13  ,   3   ,   99  ,   177 ,   507 ,   1017    ,   1565    ,   757 ,   5829    ,0 };
            const std::uint32_t dim824JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   7   ,   49  ,   51  ,   71  ,   177 ,   1015    ,   1321    ,   187 ,   875 ,0 };
            const std::uint32_t dim825JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   29  ,   49  ,   111 ,   143 ,   99  ,   297 ,   659 ,   3147    ,   7531    ,0 };
            const std::uint32_t dim826JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   3   ,   15  ,   21  ,   11  ,   229 ,   249 ,   185 ,   147 ,   173 ,   7895    ,0 };
            const std::uint32_t dim827JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   17  ,   23  ,   123 ,   157 ,   373 ,   501 ,   411 ,   2487    ,   4873    ,0 };
            const std::uint32_t dim828JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   21  ,   61  ,   83  ,   65  ,   345 ,   105 ,   1533    ,   981 ,   1635    ,0 };
            const std::uint32_t dim829JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   15  ,   15  ,   19  ,   119 ,   59  ,   1003    ,   1595    ,   2871    ,   627 ,0 };
            const std::uint32_t dim830JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   7   ,   47  ,   43  ,   3   ,   359 ,   175 ,   1149    ,   213 ,   79  ,0 };
            const std::uint32_t dim831JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   5   ,   19  ,   7   ,   93  ,   335 ,   809 ,   1867    ,   1359    ,   1017    ,0 };
            const std::uint32_t dim832JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   31  ,   25  ,   75  ,   139 ,   125 ,   479 ,   101 ,   3969    ,   1173    ,0 };
            const std::uint32_t dim833JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   5   ,   17  ,   33  ,   145 ,   57  ,   31  ,   1033    ,   3975    ,   5561    ,0 };
            const std::uint32_t dim834JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   31  ,   37  ,   47  ,   149 ,   341 ,   663 ,   303 ,   3395    ,   4327    ,0 };
            const std::uint32_t dim835JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   31  ,   31  ,   37  ,   207 ,   189 ,   435 ,   347 ,   2791    ,   2203    ,0 };
            const std::uint32_t dim836JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   3   ,   61  ,   71  ,   199 ,   207 ,   261 ,   27  ,   2281    ,   6215    ,0 };
            const std::uint32_t dim837JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   13  ,   19  ,   61  ,   51  ,   99  ,   279 ,   535 ,   473 ,   2233    ,   5637    ,0 };
            const std::uint32_t dim838JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   7   ,   51  ,   25  ,   159 ,   63  ,   611 ,   1015    ,   3561    ,   5763    ,0 };
            const std::uint32_t dim839JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   9   ,   13  ,   101 ,   13  ,   203 ,   733 ,   1657    ,   919 ,   7857    ,0 };
            const std::uint32_t dim840JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   5   ,   7   ,   105 ,   137 ,   321 ,   817 ,   467 ,   4043    ,   603 ,0 };
            const std::uint32_t dim841JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   5   ,   7   ,   105 ,   93  ,   295 ,   617 ,   713 ,   3075    ,   1839    ,0 };
            const std::uint32_t dim842JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   11  ,   17  ,   89  ,   229 ,   417 ,   53  ,   693 ,   2101    ,   1293    ,0 };
            const std::uint32_t dim843JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   3   ,   57  ,   95  ,   175 ,   161 ,   291 ,   219 ,   3101    ,   3387    ,0 };
            const std::uint32_t dim844JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   25  ,   53  ,   89  ,   7   ,   9   ,   863 ,   675 ,   1011    ,   1753    ,0 };
            const std::uint32_t dim845JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   15  ,   13  ,   41  ,   57  ,   141 ,   109 ,   541 ,   387 ,   3805    ,   2219    ,0 };
            const std::uint32_t dim846JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   19  ,   45  ,   45  ,   63  ,   283 ,   277 ,   1503    ,   3909    ,   4825    ,0 };
            const std::uint32_t dim847JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   11  ,   27  ,   33  ,   245 ,   335 ,   785 ,   1651    ,   2503    ,   7247    ,0 };
            const std::uint32_t dim848JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   19  ,   3   ,   29  ,   9   ,   259 ,   1023    ,   71  ,   3659    ,   3615    ,0 };
            const std::uint32_t dim849JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   29  ,   41  ,   59  ,   137 ,   139 ,   193 ,   267 ,   3293    ,   4769    ,0 };
            const std::uint32_t dim850JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   21  ,   29  ,   107 ,   227 ,   107 ,   929 ,   1009    ,   2013    ,   2791    ,0 };
            const std::uint32_t dim851JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   7   ,   25  ,   61  ,   105 ,   159 ,   125 ,   873 ,   293 ,   1475    ,   1745    ,0 };
            const std::uint32_t dim852JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   13  ,   11  ,   63  ,   109 ,   329 ,   847 ,   521 ,   3045    ,   2673    ,0 };
            const std::uint32_t dim853JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   1   ,   21  ,   1   ,   15  ,   161 ,   369 ,   339 ,   417 ,   3165    ,   5047    ,0 };
            const std::uint32_t dim854JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   31  ,   61  ,   109 ,   25  ,   491 ,   969 ,   1369    ,   403 ,   835 ,0 };
            const std::uint32_t dim855JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   29  ,   29  ,   27  ,   55  ,   395 ,   979 ,   27  ,   3091    ,   2383    ,0 };
            const std::uint32_t dim856JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   25  ,   17  ,   73  ,   117 ,   55  ,   381 ,   641 ,   2549    ,   7049    ,0 };
            const std::uint32_t dim857JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   17  ,   5   ,   97  ,   89  ,   187 ,   973 ,   1343    ,   3777    ,   3549    ,0 };
            const std::uint32_t dim858JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   9   ,   51  ,   49  ,   169 ,   135 ,   827 ,   1941    ,   3421    ,   2351    ,0 };
            const std::uint32_t dim859JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   25  ,   59  ,   9   ,   63  ,   259 ,   551 ,   983 ,   2743    ,   3439    ,0 };
            const std::uint32_t dim860JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   1   ,   55  ,   19  ,   35  ,   39  ,   629 ,   1601    ,   773 ,   3697    ,0 };
            const std::uint32_t dim861JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   17  ,   59  ,   55  ,   201 ,   467 ,   945 ,   707 ,   2197    ,   6907    ,0 };
            const std::uint32_t dim862JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   11  ,   9   ,   1   ,   87  ,   299 ,   509 ,   117 ,   3249    ,   3811    ,0 };
            const std::uint32_t dim863JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   23  ,   35  ,   43  ,   129 ,   357 ,   501 ,   837 ,   305 ,   7967    ,0 };
            const std::uint32_t dim864JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   23  ,   45  ,   85  ,   245 ,   157 ,   193 ,   215 ,   1021    ,   5115    ,0 };
            const std::uint32_t dim865JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   9   ,   5   ,   47  ,   125 ,   27  ,   295 ,   407 ,   1601    ,   859 ,   1203    ,0 };
            const std::uint32_t dim866JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   7   ,   21  ,   3   ,   23  ,   141 ,   75  ,   841 ,   199 ,   2719    ,   2131    ,0 };
            const std::uint32_t dim867JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   3   ,   7   ,   35  ,   227 ,   275 ,   37  ,   523 ,   2849    ,   4363    ,0 };
            const std::uint32_t dim868JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   9   ,   5   ,   39  ,   95  ,   77  ,   201 ,   891 ,   339 ,   375 ,   7115    ,0 };
            const std::uint32_t dim869JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   3   ,   57  ,   57  ,   49  ,   305 ,   141 ,   1149    ,   3909    ,   6981    ,0 };
            const std::uint32_t dim870JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   19  ,   17  ,   53  ,   31  ,   233 ,   317 ,   1541    ,   235 ,   1831    ,0 };
            const std::uint32_t dim871JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   7   ,   63  ,   125 ,   169 ,   141 ,   399 ,   277 ,   1417    ,   7989    ,0 };
            const std::uint32_t dim872JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   17  ,   61  ,   89  ,   11  ,   411 ,   505 ,   1191    ,   2651    ,   1175    ,0 };
            const std::uint32_t dim873JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   11  ,   41  ,   39  ,   69  ,   279 ,   229 ,   1247    ,   1001    ,   7163    ,0 };
            const std::uint32_t dim874JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   5   ,   13  ,   29  ,   115 ,   51  ,   79  ,   57  ,   315 ,   173 ,   5875    ,0 };
            const std::uint32_t dim875JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   1   ,   43  ,   121 ,   5   ,   99  ,   451 ,   1121    ,   425 ,   4581    ,0 };
            const std::uint32_t dim876JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   19  ,   5   ,   101 ,   33  ,   19  ,   5   ,   1325    ,   3527    ,   1733    ,0 };
            const std::uint32_t dim877JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   7   ,   15  ,   35  ,   91  ,   141 ,   127 ,   1005    ,   459 ,   3707    ,   6551    ,0 };
            const std::uint32_t dim878JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   15  ,   27  ,   31  ,   49  ,   153 ,   337 ,   1235    ,   2063    ,   211 ,0 };
            const std::uint32_t dim879JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   25  ,   45  ,   17  ,   233 ,   161 ,   559 ,   1687    ,   3833    ,   5451    ,0 };
            const std::uint32_t dim880JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   23  ,   39  ,   127 ,   183 ,   379 ,   655 ,   129 ,   37  ,   2283    ,0 };
            const std::uint32_t dim881JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   23  ,   33  ,   35  ,   111 ,   491 ,   343 ,   1771    ,   509 ,   937 ,0 };
            const std::uint32_t dim882JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   19  ,   59  ,   59  ,   79  ,   327 ,   911 ,   1103    ,   2695    ,   3673    ,0 };
            const std::uint32_t dim883JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   11  ,   23  ,   43  ,   31  ,   455 ,   843 ,   1515    ,   3059    ,   505 ,0 };
            const std::uint32_t dim884JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   15  ,   1   ,   63  ,   35  ,   327 ,   801 ,   237 ,   1137    ,   3447    ,0 };
            const std::uint32_t dim885JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   7   ,   35  ,   105 ,   113 ,   281 ,   153 ,   461 ,   3165    ,   659 ,0 };
            const std::uint32_t dim886JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   29  ,   5   ,   119 ,   45  ,   313 ,   713 ,   1989    ,   99  ,   883 ,0 };
            const std::uint32_t dim887JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   17  ,   43  ,   115 ,   201 ,   51  ,   947 ,   1271    ,   2465    ,   5319    ,0 };
            const std::uint32_t dim888JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   25  ,   39  ,   49  ,   103 ,   99  ,   469 ,   1777    ,   33  ,   7115    ,0 };
            const std::uint32_t dim889JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   17  ,   43  ,   53  ,   97  ,   473 ,   231 ,   1035    ,   19  ,   995 ,0 };
            const std::uint32_t dim890JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   5   ,   1   ,   89  ,   255 ,   201 ,   945 ,   2017    ,   3181    ,   3961    ,0 };
            const std::uint32_t dim891JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   9   ,   9   ,   45  ,   91  ,   451 ,   671 ,   613 ,   4051    ,   1233    ,0 };
            const std::uint32_t dim892JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   27  ,   49  ,   37  ,   151 ,   59  ,   489 ,   341 ,   507 ,   5839    ,0 };
            const std::uint32_t dim893JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   1   ,   41  ,   11  ,   165 ,   509 ,   615 ,   793 ,   2741    ,   7269    ,0 };
            const std::uint32_t dim894JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   11  ,   33  ,   115 ,   87  ,   131 ,   653 ,   995 ,   1903    ,   4449    ,0 };
            const std::uint32_t dim895JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   27  ,   41  ,   49  ,   211 ,   229 ,   797 ,   469 ,   839 ,   5047    ,0 };
            const std::uint32_t dim896JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   9   ,   43  ,   57  ,   13  ,   77  ,   623 ,   245 ,   2349    ,   3611    ,0 };
            const std::uint32_t dim897JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   23  ,   31  ,   101 ,   3   ,   355 ,   739 ,   1287    ,   3973    ,   6923    ,0 };
            const std::uint32_t dim898JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   5   ,   17  ,   61  ,   83  ,   75  ,   329 ,   849 ,   645 ,   3125    ,   8159    ,0 };
            const std::uint32_t dim899JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   15  ,   31  ,   91  ,   149 ,   195 ,   585 ,   1415    ,   119 ,   6737    ,0 };
            const std::uint32_t dim900JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   7   ,   3   ,   41  ,   25  ,   481 ,   175 ,   1147    ,   153 ,   6483    ,0 };
            const std::uint32_t dim901JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   1   ,   29  ,   59  ,   11  ,   225 ,   275 ,   299 ,   1083    ,   401 ,   6809    ,0 };
            const std::uint32_t dim902JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   7   ,   19  ,   119 ,   145 ,   299 ,   273 ,   1571    ,   627 ,   6597    ,0 };
            const std::uint32_t dim903JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   13  ,   17  ,   7   ,   63  ,   19  ,   141 ,   359 ,   879 ,   2741    ,   3139    ,0 };
            const std::uint32_t dim904JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   9   ,   19  ,   45  ,   127 ,   511 ,   767 ,   47  ,   2389    ,   7691    ,0 };
            const std::uint32_t dim905JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   15  ,   11  ,   53  ,   15  ,   207 ,   31  ,   215 ,   183 ,   2745    ,   4703    ,0 };
            const std::uint32_t dim906JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   13  ,   43  ,   13  ,   65  ,   165 ,   157 ,   1139    ,   2417    ,   547 ,0 };
            const std::uint32_t dim907JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   29  ,   29  ,   45  ,   165 ,   401 ,   327 ,   119 ,   1449    ,   1281    ,0 };
            const std::uint32_t dim908JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   27  ,   25  ,   35  ,   5   ,   447 ,   205 ,   1487    ,   4089    ,   4929    ,0 };
            const std::uint32_t dim909JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   3   ,   45  ,   73  ,   19  ,   349 ,   657 ,   771 ,   1029    ,   5047    ,0 };
            const std::uint32_t dim910JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   29  ,   63  ,   23  ,   69  ,   425 ,   997 ,   9   ,   2365    ,   3279    ,0 };
            const std::uint32_t dim911JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   7   ,   31  ,   47  ,   205 ,   29  ,   851 ,   1735    ,   1641    ,   2623    ,0 };
            const std::uint32_t dim912JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   25  ,   33  ,   73  ,   109 ,   183 ,   357 ,   1585    ,   3323    ,   4993    ,0 };
            const std::uint32_t dim913JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   13  ,   53  ,   43  ,   61  ,   137 ,   127 ,   1769    ,   2107    ,   4025    ,0 };
            const std::uint32_t dim914JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   25  ,   59  ,   93  ,   57  ,   391 ,   155 ,   1367    ,   4093    ,   625 ,0 };
            const std::uint32_t dim915JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   25  ,   27  ,   53  ,   217 ,   75  ,   961 ,   371 ,   1281    ,   6553    ,0 };
            const std::uint32_t dim916JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   19  ,   5   ,   89  ,   87  ,   377 ,   199 ,   1533    ,   2219    ,   2705    ,0 };
            const std::uint32_t dim917JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   15  ,   1   ,   61  ,   143 ,   137 ,   379 ,   1443    ,   355 ,   971 ,0 };
            const std::uint32_t dim918JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   17  ,   57  ,   85  ,   225 ,   37  ,   345 ,   1509    ,   597 ,   5731    ,0 };
            const std::uint32_t dim919JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   29  ,   55  ,   69  ,   27  ,   155 ,   481 ,   925 ,   3391    ,   5277    ,0 };
            const std::uint32_t dim920JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   9   ,   15  ,   19  ,   25  ,   5   ,   109 ,   83  ,   635 ,   3073    ,   3531    ,0 };
            const std::uint32_t dim921JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   23  ,   5   ,   13  ,   7   ,   19  ,   625 ,   1481    ,   1827    ,   3991    ,0 };
            const std::uint32_t dim922JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   7   ,   35  ,   123 ,   161 ,   303 ,   423 ,   25  ,   2467    ,   3411    ,0 };
            const std::uint32_t dim923JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   9   ,   47  ,   27  ,   159 ,   249 ,   573 ,   1987    ,   3449    ,   7639    ,0 };
            const std::uint32_t dim924JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   19  ,   59  ,   7   ,   209 ,   27  ,   495 ,   1491    ,   3217    ,   1321    ,0 };
            const std::uint32_t dim925JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   11  ,   17  ,   11  ,   109 ,   87  ,   315 ,   917 ,   1105    ,   215 ,   1295    ,0 };
            const std::uint32_t dim926JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   9   ,   25  ,   11  ,   77  ,   81  ,   453 ,   871 ,   1541    ,   141 ,   1625    ,0 };
            const std::uint32_t dim927JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   1   ,   37  ,   11  ,   149 ,   45  ,   213 ,   975 ,   2557    ,   4263    ,0 };
            const std::uint32_t dim928JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   17  ,   55  ,   59  ,   33  ,   39  ,   285 ,   1767    ,   3687    ,   7087    ,0 };
            const std::uint32_t dim929JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   7   ,   27  ,   9   ,   103 ,   191 ,   405 ,   25  ,   595 ,   1765    ,   5695    ,0 };
            const std::uint32_t dim930JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   7   ,   31  ,   27  ,   29  ,   195 ,   355 ,   199 ,   1297    ,   3195    ,   683 ,0 };
            const std::uint32_t dim931JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   1   ,   21  ,   3   ,   19  ,   227 ,   325 ,   279 ,   1593    ,   613 ,   7527    ,0 };
            const std::uint32_t dim932JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   27  ,   17  ,   91  ,   179 ,   385 ,   133 ,   823 ,   3731    ,   2957    ,0 };
            const std::uint32_t dim933JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   7   ,   13  ,   9   ,   1   ,   137 ,   347 ,   67  ,   287 ,   1403    ,   5233    ,0 };
            const std::uint32_t dim934JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   17  ,   15  ,   25  ,   95  ,   225 ,   469 ,   1585    ,   2513    ,   1489    ,0 };
            const std::uint32_t dim935JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   31  ,   33  ,   81  ,   121 ,   435 ,   971 ,   877 ,   1603    ,   373 ,0 };
            const std::uint32_t dim936JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   9   ,   7   ,   31  ,   29  ,   27  ,   135 ,   181 ,   549 ,   1901    ,   813 ,0 };
            const std::uint32_t dim937JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   3   ,   3   ,   5   ,   11  ,   229 ,   255 ,   981 ,   1843    ,   2785    ,   2573    ,0 };
            const std::uint32_t dim938JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   13  ,   25  ,   29  ,   13  ,   87  ,   361 ,   431 ,   969 ,   1893    ,   5257    ,0 };
            const std::uint32_t dim939JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   3   ,   21  ,   53  ,   99  ,   243 ,   313 ,   681 ,   655 ,   2733    ,   4329    ,0 };
            const std::uint32_t dim940JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   13  ,   3   ,   107 ,   61  ,   285 ,   687 ,   213 ,   551 ,   5039    ,0 };
            const std::uint32_t dim941JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   3   ,   9   ,   47  ,   99  ,   239 ,   313 ,   975 ,   1403    ,   3641    ,   1951    ,0 };
            const std::uint32_t dim942JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   19  ,   43  ,   77  ,   139 ,   357 ,   973 ,   977 ,   369 ,   2775    ,0 };
            const std::uint32_t dim943JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   23  ,   43  ,   109 ,   91  ,   321 ,   1   ,   1917    ,   3341    ,   1441    ,0 };
            const std::uint32_t dim944JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   9   ,   7   ,   19  ,   61  ,   255 ,   25  ,   729 ,   479 ,   837 ,   13  ,0 };
            const std::uint32_t dim945JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   27  ,   29  ,   123 ,   101 ,   349 ,   443 ,   1759    ,   3   ,   4685    ,0 };
            const std::uint32_t dim946JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   29  ,   47  ,   33  ,   183 ,   223 ,   927 ,   1341    ,   797 ,   8007    ,0 };
            const std::uint32_t dim947JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   27  ,   33  ,   71  ,   195 ,   57  ,   897 ,   1337    ,   3455    ,   5201    ,0 };
            const std::uint32_t dim948JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   31  ,   55  ,   121 ,   49  ,   343 ,   501 ,   1511    ,   113 ,   1549    ,0 };
            const std::uint32_t dim949JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   3   ,   9   ,   61  ,   19  ,   215 ,   323 ,   427 ,   1777    ,   685 ,   63  ,0 };
            const std::uint32_t dim950JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   15  ,   17  ,   23  ,   33  ,   129 ,   257 ,   527 ,   825 ,   3611    ,   2123    ,0 };
            const std::uint32_t dim951JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   5   ,   45  ,   79  ,   9   ,   211 ,   493 ,   1095    ,   3031    ,   4093    ,0 };
            const std::uint32_t dim952JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   21  ,   29  ,   29  ,   247 ,   489 ,   735 ,   11  ,   1723    ,   4459    ,0 };
            const std::uint32_t dim953JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   21  ,   41  ,   59  ,   65  ,   151 ,   113 ,   851 ,   1213    ,   6367    ,0 };
            const std::uint32_t dim954JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   9   ,   17  ,   85  ,   207 ,   219 ,   45  ,   85  ,   2433    ,   2219    ,0 };
            const std::uint32_t dim955JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   5   ,   7   ,   9   ,   39  ,   201 ,   369 ,   369 ,   113 ,   2667    ,   5137    ,0 };
            const std::uint32_t dim956JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   3   ,   27  ,   59  ,   127 ,   189 ,   289 ,   683 ,   1285    ,   2713    ,   7037    ,0 };
            const std::uint32_t dim957JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   3   ,   5   ,   19  ,   51  ,   23  ,   139 ,   379 ,   651 ,   19  ,   7705    ,0 };
            const std::uint32_t dim958JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   11  ,   31  ,   23  ,   11  ,   37  ,   161 ,   679 ,   1581    ,   217 ,   7973    ,0 };
            const std::uint32_t dim959JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   9   ,   49  ,   23  ,   177 ,   475 ,   261 ,   403 ,   1415    ,   2299    ,0 };
            const std::uint32_t dim960JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   19  ,   35  ,   117 ,   223 ,   159 ,   805 ,   1039    ,   1359    ,   6635    ,0 };
            const std::uint32_t dim961JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   19  ,   1   ,   121 ,   223 ,   123 ,   161 ,   1631    ,   1161    ,   6997    ,0 };
            const std::uint32_t dim962JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   5   ,   31  ,   41  ,   133 ,   121 ,   523 ,   1941    ,   2583    ,   6231    ,0 };
            const std::uint32_t dim963JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   15  ,   7   ,   31  ,   95  ,   49  ,   501 ,   737 ,   363 ,   2879    ,   6561    ,0 };
            const std::uint32_t dim964JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   11  ,   31  ,   47  ,   61  ,   17  ,   399 ,   3   ,   605 ,   907 ,   4605    ,0 };
            const std::uint32_t dim965JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   1   ,   23  ,   61  ,   47  ,   93  ,   25  ,   643 ,   881 ,   3559    ,   5251    ,0 };
            const std::uint32_t dim966JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   5   ,   27  ,   63  ,   1   ,   147 ,   425 ,   639 ,   1229    ,   3131    ,   5833    ,0 };
            const std::uint32_t dim967JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   31  ,   31  ,   57  ,   121 ,   183 ,   39  ,   1067    ,   1915    ,   7321    ,0 };
            const std::uint32_t dim968JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   9   ,   21  ,   25  ,   125 ,   29  ,   53  ,   433 ,   189 ,   3465    ,   3847    ,0 };
            const std::uint32_t dim969JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   1   ,   11  ,   13  ,   99  ,   229 ,   365 ,   909 ,   87  ,   3669    ,   6609    ,0 };
            const std::uint32_t dim970JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   1   ,   29  ,   3   ,   43  ,   13  ,   19  ,   897 ,   1269    ,   1091    ,   3207    ,0 };
            const std::uint32_t dim971JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   11  ,   33  ,   69  ,   251 ,   337 ,   235 ,   523 ,   2053    ,   3655    ,0 };
            const std::uint32_t dim972JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   1   ,   11  ,   75  ,   169 ,   507 ,   391 ,   1009    ,   3165    ,   3691    ,0 };
            const std::uint32_t dim973JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   13  ,   3   ,   39  ,   119 ,   193 ,   169 ,   661 ,   813 ,   143 ,   7825    ,0 };
            const std::uint32_t dim974JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   11  ,   13  ,   33  ,   91  ,   209 ,   469 ,   141 ,   391 ,   1037    ,   6591    ,0 };
            const std::uint32_t dim975JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   17  ,   45  ,   39  ,   19  ,   449 ,   691 ,   187 ,   2739    ,   7671    ,0 };
            const std::uint32_t dim976JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   15  ,   13  ,   57  ,   7   ,   75  ,   435 ,   287 ,   1479    ,   2143    ,   6501    ,0 };
            const std::uint32_t dim977JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   11  ,   11  ,   29  ,   111 ,   223 ,   505 ,   139 ,   1587    ,   3769    ,   5839    ,0 };
            const std::uint32_t dim978JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   7   ,   5   ,   61  ,   7   ,   209 ,   461 ,   37  ,   1771    ,   3683    ,   4283    ,0 };
            const std::uint32_t dim979JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   9   ,   1   ,   5   ,   123 ,   69  ,   75  ,   451 ,   963 ,   3273    ,   2785    ,0 };
            const std::uint32_t dim980JoeKuoD5Init[]    =   {   1   ,   1   ,   1   ,   3   ,   7   ,   17  ,   87  ,   63  ,   505 ,   863 ,   1955    ,   3253    ,   463 ,0 };
            const std::uint32_t dim981JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   15  ,   15  ,   55  ,   127 ,   213 ,   277 ,   829 ,   165 ,   2885    ,   6693    ,0 };
            const std::uint32_t dim982JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   1   ,   9   ,   35  ,   5   ,   233 ,   329 ,   827 ,   531 ,   1435    ,   899 ,0 };
            const std::uint32_t dim983JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   15  ,   25  ,   19  ,   233 ,   375 ,   327 ,   241 ,   3519    ,   4511    ,0 };
            const std::uint32_t dim984JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   11  ,   1   ,   1   ,   117 ,   29  ,   185 ,   529 ,   873 ,   1769    ,   6857    ,0 };
            const std::uint32_t dim985JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   11  ,   1   ,   31  ,   125 ,   27  ,   77  ,   295 ,   43  ,   205 ,   3349    ,0 };
            const std::uint32_t dim986JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   1   ,   59  ,   11  ,   195 ,   483 ,   391 ,   381 ,   1251    ,   205 ,0 };
            const std::uint32_t dim987JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   1   ,   5   ,   51  ,   33  ,   159 ,   143 ,   213 ,   573 ,   1329    ,   2327    ,0 };
            const std::uint32_t dim988JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   25  ,   5   ,   11  ,   203 ,   217 ,   397 ,   819 ,   949 ,   3987    ,0 };
            const std::uint32_t dim989JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   17  ,   1   ,   29  ,   219 ,   161 ,   437 ,   685 ,   2743    ,   7509    ,0 };
            const std::uint32_t dim990JoeKuoD5Init[]    =   {   1   ,   1   ,   3   ,   13  ,   3   ,   31  ,   29  ,   51  ,   41  ,   217 ,   997 ,   2581    ,   4273    ,0 };
            const std::uint32_t dim991JoeKuoD5Init[]    =   {   1   ,   1   ,   7   ,   5   ,   31  ,   33  ,   45  ,   113 ,   463 ,   537 ,   237 ,   1501    ,   315 ,0 };
            const std::uint32_t dim992JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   5   ,   13  ,   3   ,   49  ,   155 ,   175 ,   655 ,   1995    ,   2131    ,   6105    ,0 };
            const std::uint32_t dim993JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   15  ,   23  ,   3   ,   17  ,   165 ,   67  ,   137 ,   337 ,   3805    ,   257 ,0 };
            const std::uint32_t dim994JoeKuoD5Init[]    =   {   1   ,   1   ,   5   ,   13  ,   31  ,   11  ,   39  ,   111 ,   79  ,   585 ,   1911    ,   2395    ,   6239    ,0 };
            const std::uint32_t dim995JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   5   ,   13  ,   61  ,   87  ,   309 ,   571 ,   321 ,   2485    ,   807 ,0 };
            const std::uint32_t dim996JoeKuoD5Init[]    =   {   1   ,   3   ,   5   ,   13  ,   31  ,   21  ,   9   ,   177 ,   9   ,   395 ,   351 ,   529 ,   4977    ,0 };
            const std::uint32_t dim997JoeKuoD5Init[]    =   {   1   ,   3   ,   1   ,   5   ,   5   ,   41  ,   95  ,   145 ,   319 ,   339 ,   1559    ,   203 ,   2883    ,0 };
            const std::uint32_t dim998JoeKuoD5Init[]    =   {   1   ,   3   ,   3   ,   7   ,   9   ,   13  ,   121 ,   111 ,   107 ,   421 ,   1763    ,   2671    ,   259 ,0 };
            const std::uint32_t dim999JoeKuoD5Init[]    =   {   1   ,   3   ,   7   ,   13  ,   25  ,   47  ,   71  ,   249 ,   119 ,   83  ,   1651    ,   2715    ,   4819    ,0 };
            const std::uint32_t dim1000JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   5   ,   59  ,   99  ,   139 ,   435 ,   653 ,   153 ,   3605    ,   753 ,0 };
            const std::uint32_t dim1001JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   19  ,   13  ,   3   ,   17  ,   215 ,   1017    ,   1685    ,   3795    ,   2363    ,0 };
            const std::uint32_t dim1002JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   15  ,   13  ,   97  ,   145 ,   383 ,   39  ,   667 ,   1217    ,   1473    ,0 };
            const std::uint32_t dim1003JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   11  ,   25  ,   107 ,   149 ,   11  ,   835 ,   1013    ,   1587    ,   1485    ,0 };
            const std::uint32_t dim1004JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   15  ,   33  ,   15  ,   251 ,   473 ,   723 ,   959 ,   3991    ,   7145    ,0 };
            const std::uint32_t dim1005JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   1   ,   49  ,   73  ,   195 ,   139 ,   893 ,   1677    ,   707 ,   667 ,0 };
            const std::uint32_t dim1006JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   23  ,   3   ,   79  ,   255 ,   371 ,   885 ,   469 ,   3673    ,   5477    ,0 };
            const std::uint32_t dim1007JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   21  ,   1   ,   45  ,   65  ,   403 ,   129 ,   123 ,   1171    ,   8177    ,0 };
            const std::uint32_t dim1008JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   29  ,   25  ,   89  ,   231 ,   81  ,   503 ,   629 ,   1925    ,   2853    ,0 };
            const std::uint32_t dim1009JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   9   ,   15  ,   107 ,   81  ,   479 ,   235 ,   1483    ,   3593    ,   2289    ,0 };
            const std::uint32_t dim1010JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   9   ,   49  ,   119 ,   161 ,   233 ,   321 ,   1505    ,   3969    ,   3131    ,0 };
            const std::uint32_t dim1011JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   9   ,   5   ,   91  ,   57  ,   13  ,   271 ,   999 ,   747 ,   3399    ,0 };
            const std::uint32_t dim1012JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   1   ,   21  ,   1   ,   179 ,   449 ,   963 ,   33  ,   2259    ,   259 ,0 };
            const std::uint32_t dim1013JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   7   ,   11  ,   81  ,   53  ,   157 ,   373 ,   767 ,   2489    ,   2275    ,0 };
            const std::uint32_t dim1014JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   9   ,   55  ,   123 ,   135 ,   9   ,   499 ,   3   ,   2039    ,   2387    ,0 };
            const std::uint32_t dim1015JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   7   ,   47  ,   119 ,   81  ,   351 ,   949 ,   1159    ,   859 ,   99  ,0 };
            const std::uint32_t dim1016JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   1   ,   5   ,   83  ,   3   ,   387 ,   455 ,   1997    ,   1253    ,   77  ,0 };
            const std::uint32_t dim1017JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   13  ,   49  ,   111 ,   133 ,   193 ,   893 ,   1549    ,   4003    ,   3461    ,0 };
            const std::uint32_t dim1018JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   21  ,   3   ,   63  ,   209 ,   491 ,   447 ,   1635    ,   2297    ,   7667    ,0 };
            const std::uint32_t dim1019JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   3   ,   61  ,   93  ,   115 ,   417 ,   465 ,   1075    ,   2157    ,   861 ,0 };
            const std::uint32_t dim1020JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   7   ,   33  ,   7   ,   61  ,   509 ,   539 ,   1579    ,   2089    ,   5633    ,0 };
            const std::uint32_t dim1021JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   9   ,   5   ,   75  ,   125 ,   345 ,   133 ,   1699    ,   3183    ,   5403    ,0 };
            const std::uint32_t dim1022JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   17  ,   9   ,   115 ,   213 ,   417 ,   713 ,   989 ,   3987    ,   3043    ,0 };
            const std::uint32_t dim1023JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   25  ,   9   ,   115 ,   83  ,   255 ,   695 ,   471 ,   1819    ,   2661    ,0 };
            const std::uint32_t dim1024JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   31  ,   35  ,   33  ,   197 ,   335 ,   543 ,   323 ,   3241    ,   7039    ,0 };
            const std::uint32_t dim1025JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   23  ,   5   ,   23  ,   193 ,   327 ,   3   ,   1425    ,   2787    ,   5659    ,0 };
            const std::uint32_t dim1026JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   27  ,   25  ,   37  ,   241 ,   373 ,   411 ,   783 ,   621 ,   2129    ,0 };
            const std::uint32_t dim1027JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   13  ,   19  ,   119 ,   39  ,   303 ,   383 ,   1965    ,   725 ,   1909    ,0 };
            const std::uint32_t dim1028JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   25  ,   27  ,   121 ,   245 ,   165 ,   985 ,   595 ,   3325    ,   7319    ,0 };
            const std::uint32_t dim1029JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   25  ,   7   ,   109 ,   75  ,   277 ,   25  ,   715 ,   495 ,   3911    ,0 };
            const std::uint32_t dim1030JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   21  ,   37  ,   13  ,   23  ,   161 ,   907 ,   1551    ,   2453    ,   5323    ,0 };
            const std::uint32_t dim1031JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   17  ,   11  ,   101 ,   237 ,   219 ,   735 ,   1865    ,   209 ,   5605    ,0 };
            const std::uint32_t dim1032JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   5   ,   63  ,   87  ,   173 ,   299 ,   739 ,   617 ,   1883    ,   2525    ,0 };
            const std::uint32_t dim1033JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   11  ,   5   ,   25  ,   207 ,   271 ,   471 ,   921 ,   3819    ,   5627    ,0 };
            const std::uint32_t dim1034JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   1   ,   7   ,   27  ,   185 ,   245 ,   629 ,   1329    ,   611 ,   7183    ,0 };
            const std::uint32_t dim1035JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   9   ,   21  ,   55  ,   17  ,   157 ,   987 ,   553 ,   3823    ,   6923    ,0 };
            const std::uint32_t dim1036JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   19  ,   47  ,   113 ,   149 ,   495 ,   891 ,   1885    ,   2699    ,   6019    ,0 };
            const std::uint32_t dim1037JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   23  ,   53  ,   27  ,   241 ,   453 ,   103 ,   1879    ,   289 ,   5195    ,0 };
            const std::uint32_t dim1038JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   13  ,   37  ,   125 ,   83  ,   341 ,   793 ,   193 ,   297 ,   3337    ,0 };
            const std::uint32_t dim1039JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   13  ,   43  ,   101 ,   121 ,   319 ,   845 ,   601 ,   3357    ,   3037    ,0 };
            const std::uint32_t dim1040JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   27  ,   3   ,   53  ,   111 ,   287 ,   791 ,   2017    ,   3869    ,   5105    ,0 };
            const std::uint32_t dim1041JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   19  ,   33  ,   107 ,   203 ,   135 ,   783 ,   497 ,   1007    ,   4587    ,0 };
            const std::uint32_t dim1042JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   7   ,   41  ,   101 ,   59  ,   407 ,   525 ,   1941    ,   961 ,   7059    ,0 };
            const std::uint32_t dim1043JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   17  ,   33  ,   9   ,   217 ,   31  ,   695 ,   1111    ,   391 ,   5617    ,0 };
            const std::uint32_t dim1044JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   15  ,   13  ,   107 ,   223 ,   477 ,   91  ,   449 ,   901 ,   3075    ,0 };
            const std::uint32_t dim1045JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   31  ,   47  ,   97  ,   49  ,   47  ,   301 ,   305 ,   1159    ,   6977    ,0 };
            const std::uint32_t dim1046JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   29  ,   9   ,   17  ,   237 ,   461 ,   593 ,   495 ,   1099    ,   5135    ,0 };
            const std::uint32_t dim1047JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   3   ,   51  ,   5   ,   113 ,   409 ,   777 ,   1323    ,   2719    ,   3647    ,0 };
            const std::uint32_t dim1048JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   15  ,   45  ,   33  ,   49  ,   167 ,   933 ,   1831    ,   3195    ,   3121    ,0 };
            const std::uint32_t dim1049JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   3   ,   33  ,   123 ,   19  ,   173 ,   69  ,   593 ,   3709    ,   7193    ,0 };
            const std::uint32_t dim1050JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   9   ,   9   ,   63  ,   81  ,   325 ,   473 ,   1517    ,   3483    ,   7585    ,0 };
            const std::uint32_t dim1051JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   31  ,   47  ,   77  ,   67  ,   55  ,   673 ,   1963    ,   111 ,   839 ,0 };
            const std::uint32_t dim1052JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   23  ,   45  ,   5   ,   159 ,   225 ,   595 ,   1573    ,   1891    ,   301 ,0 };
            const std::uint32_t dim1053JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   3   ,   21  ,   123 ,   29  ,   331 ,   793 ,   1885    ,   3299    ,   3433    ,0 };
            const std::uint32_t dim1054JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   23  ,   51  ,   21  ,   23  ,   265 ,   919 ,   853 ,   3969    ,   2043    ,0 };
            const std::uint32_t dim1055JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   25  ,   59  ,   111 ,   13  ,   217 ,   893 ,   1005    ,   3795    ,   3233    ,0 };
            const std::uint32_t dim1056JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   7   ,   11  ,   69  ,   183 ,   509 ,   51  ,   727 ,   2093    ,   2615    ,0 };
            const std::uint32_t dim1057JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   3   ,   13  ,   119 ,   209 ,   365 ,   895 ,   1563    ,   427 ,   5519    ,0 };
            const std::uint32_t dim1058JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   23  ,   9   ,   87  ,   29  ,   19  ,   519 ,   763 ,   3553    ,   575 ,0 };
            const std::uint32_t dim1059JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   3   ,   21  ,   15  ,   237 ,   501 ,   627 ,   1557    ,   545 ,   2415    ,0 };
            const std::uint32_t dim1060JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   7   ,   53  ,   83  ,   19  ,   385 ,   425 ,   1145    ,   1039    ,   6667    ,0 };
            const std::uint32_t dim1061JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   31  ,   31  ,   39  ,   51  ,   233 ,   755 ,   1105    ,   925 ,   6113    ,0 };
            const std::uint32_t dim1062JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   17  ,   25  ,   45  ,   135 ,   347 ,   707 ,   1035    ,   1405    ,   7105    ,0 };
            const std::uint32_t dim1063JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   17  ,   25  ,   119 ,   77  ,   279 ,   467 ,   195 ,   1919    ,   4959    ,0 };
            const std::uint32_t dim1064JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   31  ,   41  ,   5   ,   21  ,   349 ,   607 ,   737 ,   2033    ,   2323    ,0 };
            const std::uint32_t dim1065JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   29  ,   19  ,   45  ,   223 ,   391 ,   495 ,   1905    ,   735 ,   6309    ,0 };
            const std::uint32_t dim1066JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   19  ,   9   ,   93  ,   89  ,   43  ,   297 ,   653 ,   1343    ,   5897    ,0 };
            const std::uint32_t dim1067JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   21  ,   7   ,   29  ,   187 ,   115 ,   279 ,   1029    ,   2817    ,   1349    ,0 };
            const std::uint32_t dim1068JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   5   ,   61  ,   35  ,   33  ,   151 ,   119 ,   1713    ,   1713    ,   1645    ,0 };
            const std::uint32_t dim1069JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   23  ,   21  ,   101 ,   131 ,   355 ,   75  ,   1233    ,   1677    ,   2463    ,0 };
            const std::uint32_t dim1070JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   5   ,   57  ,   79  ,   51  ,   299 ,   307 ,   1977    ,   3473    ,   6153    ,0 };
            const std::uint32_t dim1071JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   19  ,   1   ,   59  ,   69  ,   175 ,   189 ,   303 ,   43  ,   7561    ,0 };
            const std::uint32_t dim1072JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   31  ,   37  ,   117 ,   9   ,   373 ,   279 ,   1187    ,   3501    ,   715 ,0 };
            const std::uint32_t dim1073JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   1   ,   29  ,   79  ,   161 ,   223 ,   437 ,   577 ,   921 ,   5535    ,0 };
            const std::uint32_t dim1074JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   31  ,   27  ,   93  ,   63  ,   281 ,   187 ,   1739    ,   4085    ,   5669    ,0 };
            const std::uint32_t dim1075JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   11  ,   25  ,   87  ,   245 ,   339 ,   741 ,   927 ,   1279    ,   3889    ,0 };
            const std::uint32_t dim1076JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   31  ,   5   ,   45  ,   205 ,   289 ,   999 ,   361 ,   3595    ,   569 ,0 };
            const std::uint32_t dim1077JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   19  ,   23  ,   103 ,   73  ,   403 ,   85  ,   1623    ,   325 ,   5369    ,0 };
            const std::uint32_t dim1078JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   13  ,   23  ,   27  ,   155 ,   359 ,   777 ,   1751    ,   915 ,   949 ,0 };
            const std::uint32_t dim1079JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   23  ,   59  ,   57  ,   215 ,   77  ,   581 ,   369 ,   953 ,   6987    ,0 };
            const std::uint32_t dim1080JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   27  ,   55  ,   103 ,   173 ,   485 ,   771 ,   1693    ,   1227    ,   3257    ,0 };
            const std::uint32_t dim1081JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   5   ,   23  ,   95  ,   121 ,   81  ,   107 ,   1897    ,   1647    ,   3047    ,0 };
            const std::uint32_t dim1082JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   17  ,   47  ,   119 ,   83  ,   137 ,   897 ,   1893    ,   653 ,   5031    ,0 };
            const std::uint32_t dim1083JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   31  ,   3   ,   73  ,   129 ,   159 ,   529 ,   1433    ,   2313    ,   6143    ,0 };
            const std::uint32_t dim1084JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   29  ,   19  ,   123 ,   141 ,   51  ,   427 ,   935 ,   2831    ,   5799    ,0 };
            const std::uint32_t dim1085JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   31  ,   3   ,   119 ,   227 ,   37  ,   435 ,   921 ,   3313    ,   2129    ,0 };
            const std::uint32_t dim1086JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   1   ,   19  ,   75  ,   35  ,   307 ,   419 ,   813 ,   2217    ,   6603    ,0 };
            const std::uint32_t dim1087JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   17  ,   47  ,   79  ,   75  ,   47  ,   835 ,   287 ,   3361    ,   5875    ,0 };
            const std::uint32_t dim1088JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   5   ,   5   ,   3   ,   19  ,   341 ,   717 ,   45  ,   1169    ,   1305    ,0 };
            const std::uint32_t dim1089JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   3   ,   11  ,   81  ,   233 ,   195 ,   987 ,   593 ,   2495    ,   5213    ,0 };
            const std::uint32_t dim1090JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   27  ,   1   ,   29  ,   251 ,   221 ,   267 ,   593 ,   361 ,   5629    ,0 };
            const std::uint32_t dim1091JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   21  ,   33  ,   15  ,   37  ,   341 ,   301 ,   293 ,   2787    ,   3531    ,0 };
            const std::uint32_t dim1092JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   3   ,   3   ,   9   ,   7   ,   257 ,   509 ,   1545    ,   4095    ,   3309    ,0 };
            const std::uint32_t dim1093JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   11  ,   7   ,   27  ,   71  ,   317 ,   221 ,   391 ,   1257    ,   5885    ,0 };
            const std::uint32_t dim1094JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   15  ,   51  ,   29  ,   107 ,   461 ,   597 ,   961 ,   3589    ,   2325    ,0 };
            const std::uint32_t dim1095JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   29  ,   1   ,   91  ,   181 ,   477 ,   125 ,   1869    ,   3209    ,   3513    ,0 };
            const std::uint32_t dim1096JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   13  ,   17  ,   49  ,   145 ,   215 ,   1003    ,   1053    ,   1413    ,   8011    ,0 };
            const std::uint32_t dim1097JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   23  ,   63  ,   9   ,   175 ,   159 ,   627 ,   705 ,   2769    ,   2469    ,0 };
            const std::uint32_t dim1098JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   27  ,   21  ,   5   ,   61  ,   249 ,   581 ,   829 ,   2195    ,   4241    ,0 };
            const std::uint32_t dim1099JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   27  ,   39  ,   67  ,   3   ,   23  ,   819 ,   1879    ,   3775    ,   6949    ,0 };
            const std::uint32_t dim1100JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   19  ,   35  ,   93  ,   113 ,   371 ,   511 ,   811 ,   577 ,   1121    ,0 };
            const std::uint32_t dim1101JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   9   ,   25  ,   103 ,   139 ,   151 ,   177 ,   557 ,   2123    ,   6677    ,0 };
            const std::uint32_t dim1102JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   17  ,   63  ,   61  ,   241 ,   351 ,   371 ,   1745    ,   3133    ,   7663    ,0 };
            const std::uint32_t dim1103JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   19  ,   39  ,   105 ,   93  ,   77  ,   445 ,   1433    ,   1793    ,   2957    ,0 };
            const std::uint32_t dim1104JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   5   ,   15  ,   29  ,   211 ,   229 ,   887 ,   413 ,   701 ,   737 ,0 };
            const std::uint32_t dim1105JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   17  ,   7   ,   69  ,   213 ,   49  ,   91  ,   1143    ,   3743    ,   4385    ,0 };
            const std::uint32_t dim1106JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   21  ,   47  ,   41  ,   157 ,   299 ,   29  ,   751 ,   2427    ,   1521    ,0 };
            const std::uint32_t dim1107JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   29  ,   45  ,   119 ,   79  ,   141 ,   477 ,   1289    ,   515 ,   8143    ,0 };
            const std::uint32_t dim1108JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   3   ,   7   ,   123 ,   197 ,   441 ,   233 ,   1841    ,   267 ,   6553    ,0 };
            const std::uint32_t dim1109JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   3   ,   41  ,   33  ,   95  ,   271 ,   461 ,   1505    ,   2989    ,   5503    ,0 };
            const std::uint32_t dim1110JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   19  ,   15  ,   1   ,   23  ,   13  ,   737 ,   51  ,   289 ,   6731    ,0 };
            const std::uint32_t dim1111JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   15  ,   11  ,   53  ,   241 ,   17  ,   107 ,   1931    ,   3759    ,   5421    ,   1889    ,0 };
            const std::uint32_t dim1112JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   15  ,   29  ,   107 ,   163 ,   395 ,   645 ,   299 ,   799 ,   4331    ,   335 ,0 };
            const std::uint32_t dim1113JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   5   ,   47  ,   91  ,   41  ,   439 ,   319 ,   1213    ,   763 ,   6101    ,   1543    ,0 };
            const std::uint32_t dim1114JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   19  ,   51  ,   117 ,   159 ,   315 ,   767 ,   1957    ,   3655    ,   6573    ,   5419    ,0 };
            const std::uint32_t dim1115JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   23  ,   51  ,   115 ,   223 ,   125 ,   633 ,   637 ,   3443    ,   1993    ,   1887    ,0 };
            const std::uint32_t dim1116JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   27  ,   59  ,   49  ,   123 ,   49  ,   187 ,   963 ,   3893    ,   3921    ,   14411   ,0 };
            const std::uint32_t dim1117JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   29  ,   3   ,   77  ,   3   ,   79  ,   409 ,   1151    ,   3547    ,   3693    ,   8367    ,0 };
            const std::uint32_t dim1118JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   23  ,   31  ,   123 ,   133 ,   215 ,   921 ,   329 ,   1449    ,   5535    ,   9725    ,0 };
            const std::uint32_t dim1119JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   11  ,   45  ,   109 ,   117 ,   493 ,   743 ,   1473    ,   2073    ,   4771    ,   16321   ,0 };
            const std::uint32_t dim1120JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   27  ,   29  ,   25  ,   223 ,   371 ,   113 ,   1183    ,   1723    ,   6127    ,   9949    ,0 };
            const std::uint32_t dim1121JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   27  ,   55  ,   119 ,   31  ,   21  ,   849 ,   2001    ,   2541    ,   2611    ,   15429   ,0 };
            const std::uint32_t dim1122JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   17  ,   1   ,   93  ,   243 ,   311 ,   175 ,   559 ,   2177    ,   5641    ,   15293   ,0 };
            const std::uint32_t dim1123JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   25  ,   31  ,   121 ,   179 ,   169 ,   61  ,   1837    ,   2233    ,   1735    ,   6597    ,0 };
            const std::uint32_t dim1124JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   21  ,   59  ,   61  ,   239 ,   501 ,   523 ,   257 ,   573 ,   893 ,   7275    ,0 };
            const std::uint32_t dim1125JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   29  ,   33  ,   77  ,   225 ,   81  ,   879 ,   1403    ,   3279    ,   2225    ,   11571   ,0 };
            const std::uint32_t dim1126JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   15  ,   5   ,   29  ,   7   ,   157 ,   717 ,   397 ,   2079    ,   5839    ,   13297   ,0 };
            const std::uint32_t dim1127JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   17  ,   3   ,   93  ,   241 ,   301 ,   433 ,   2003    ,   2089    ,   5781    ,   15223   ,0 };
            const std::uint32_t dim1128JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   5   ,   19  ,   53  ,   189 ,   41  ,   17  ,   897 ,   2327    ,   3481    ,   7185    ,0 };
            const std::uint32_t dim1129JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   25  ,   23  ,   23  ,   155 ,   367 ,   391 ,   1001    ,   1179    ,   3781    ,   14225   ,0 };
            const std::uint32_t dim1130JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   9   ,   23  ,   63  ,   73  ,   439 ,   361 ,   233 ,   3387    ,   887 ,   5425    ,0 };
            const std::uint32_t dim1131JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   5   ,   57  ,   55  ,   35  ,   369 ,   85  ,   1585    ,   2267    ,   2927    ,   13997   ,0 };
            const std::uint32_t dim1132JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   7   ,   7   ,   55  ,   109 ,   401 ,   443 ,   1777    ,   3831    ,   6933    ,   3661    ,0 };
            const std::uint32_t dim1133JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   17  ,   27  ,   5   ,   17  ,   419 ,   949 ,   1483    ,   791 ,   7353    ,   1425    ,0 };
            const std::uint32_t dim1134JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   27  ,   41  ,   67  ,   135 ,   129 ,   863 ,   1679    ,   4001    ,   6841    ,   13561   ,0 };
            const std::uint32_t dim1135JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   21  ,   43  ,   45  ,   65  ,   103 ,   141 ,   1261    ,   2865    ,   5621    ,   5131    ,0 };
            const std::uint32_t dim1136JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   19  ,   3   ,   97  ,   159 ,   465 ,   31  ,   1757    ,   2765    ,   667 ,   6943    ,0 };
            const std::uint32_t dim1137JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   3   ,   5   ,   111 ,   203 ,   313 ,   495 ,   123 ,   1899    ,   7765    ,   2737    ,0 };
            const std::uint32_t dim1138JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   19  ,   63  ,   19  ,   233 ,   283 ,   25  ,   1009    ,   2117    ,   6233    ,   5059    ,0 };
            const std::uint32_t dim1139JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   29  ,   11  ,   35  ,   111 ,   111 ,   49  ,   1681    ,   3483    ,   2449    ,   13877   ,0 };
            const std::uint32_t dim1140JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   7   ,   61  ,   27  ,   217 ,   275 ,   137 ,   2025    ,   2745    ,   5565    ,   7999    ,0 };
            const std::uint32_t dim1141JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   13  ,   19  ,   113 ,   169 ,   425 ,   691 ,   1425    ,   1645    ,   1045    ,   9237    ,0 };
            const std::uint32_t dim1142JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   23  ,   19  ,   67  ,   5   ,   225 ,   523 ,   1809    ,   341 ,   7919    ,   3675    ,0 };
            const std::uint32_t dim1143JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   3   ,   33  ,   25  ,   229 ,   393 ,   141 ,   1953    ,   1433    ,   1593    ,   11569   ,0 };
            const std::uint32_t dim1144JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   5   ,   23  ,   53  ,   59  ,   141 ,   385 ,   1765    ,   4079    ,   2901    ,   593 ,0 };
            const std::uint32_t dim1145JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   15  ,   43  ,   115 ,   93  ,   121 ,   209 ,   1797    ,   633 ,   2595    ,   5539    ,0 };
            const std::uint32_t dim1146JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   5   ,   25  ,   9   ,   141 ,   37  ,   313 ,   1937    ,   2259    ,   1051    ,   8251    ,0 };
            const std::uint32_t dim1147JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   17  ,   1   ,   89  ,   173 ,   169 ,   463 ,   2003    ,   4005    ,   6009    ,   4373    ,0 };
            const std::uint32_t dim1148JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   17  ,   21  ,   59  ,   207 ,   333 ,   741 ,   1847    ,   683 ,   2847    ,   11007   ,0 };
            const std::uint32_t dim1149JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   5   ,   39  ,   111 ,   91  ,   49  ,   559 ,   1937    ,   1311    ,   6157    ,   517 ,0 };
            const std::uint32_t dim1150JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   29  ,   1   ,   113 ,   125 ,   343 ,   939 ,   1989    ,   2569    ,   7215    ,   5099    ,0 };
            const std::uint32_t dim1151JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   5   ,   55  ,   103 ,   237 ,   313 ,   43  ,   909 ,   201 ,   175 ,   16025   ,0 };
            const std::uint32_t dim1152JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   25  ,   29  ,   33  ,   59  ,   127 ,   865 ,   1753    ,   3649    ,   5517    ,   5001    ,0 };
            const std::uint32_t dim1153JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   27  ,   31  ,   97  ,   153 ,   451 ,   241 ,   59  ,   515 ,   2869    ,   12909   ,0 };
            const std::uint32_t dim1154JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   13  ,   51  ,   3   ,   55  ,   105 ,   497 ,   701 ,   483 ,   5165    ,   4721    ,0 };
            const std::uint32_t dim1155JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   19  ,   57  ,   39  ,   55  ,   197 ,   409 ,   199 ,   1635    ,   1965    ,   2489    ,0 };
            const std::uint32_t dim1156JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   1   ,   13  ,   123 ,   125 ,   341 ,   981 ,   1957    ,   1619    ,   1973    ,   8641    ,0 };
            const std::uint32_t dim1157JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   29  ,   13  ,   31  ,   71  ,   443 ,   867 ,   1755    ,   843 ,   7349    ,   6015    ,0 };
            const std::uint32_t dim1158JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   15  ,   39  ,   81  ,   123 ,   9   ,   991 ,   803 ,   3281    ,   7859    ,   15455   ,0 };
            const std::uint32_t dim1159JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   3   ,   33  ,   87  ,   81  ,   111 ,   595 ,   483 ,   3273    ,   847 ,   2061    ,0 };
            const std::uint32_t dim1160JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   9   ,   21  ,   79  ,   49  ,   453 ,   125 ,   603 ,   1733    ,   7213    ,   7309    ,0 };
            const std::uint32_t dim1161JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   29  ,   47  ,   21  ,   99  ,   35  ,   275 ,   69  ,   3773    ,   389 ,   10615   ,0 };
            const std::uint32_t dim1162JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   15  ,   21  ,   9   ,   55  ,   293 ,   639 ,   135 ,   903 ,   973 ,   9467    ,0 };
            const std::uint32_t dim1163JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   19  ,   63  ,   73  ,   71  ,   397 ,   387 ,   1859    ,   2741    ,   7323    ,   369 ,0 };
            const std::uint32_t dim1164JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   21  ,   23  ,   55  ,   129 ,   183 ,   721 ,   1293    ,   3579    ,   3629    ,   13303   ,0 };
            const std::uint32_t dim1165JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   21  ,   35  ,   79  ,   255 ,   443 ,   123 ,   551 ,   1113    ,   8133    ,   11621   ,0 };
            const std::uint32_t dim1166JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   19  ,   61  ,   35  ,   161 ,   145 ,   291 ,   1503    ,   3085    ,   4589    ,   7971    ,0 };
            const std::uint32_t dim1167JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   9   ,   59  ,   119 ,   133 ,   69  ,   413 ,   335 ,   2089    ,   8085    ,   12727   ,0 };
            const std::uint32_t dim1168JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   17  ,   5   ,   83  ,   125 ,   161 ,   745 ,   1889    ,   345 ,   8107    ,   10693   ,0 };
            const std::uint32_t dim1169JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   5   ,   29  ,   59  ,   69  ,   113 ,   529 ,   199 ,   1565    ,   1611    ,   12297   ,0 };
            const std::uint32_t dim1170JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   27  ,   61  ,   49  ,   59  ,   249 ,   121 ,   1569    ,   407 ,   1443    ,   5705    ,0 };
            const std::uint32_t dim1171JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   5   ,   3   ,   93  ,   99  ,   417 ,   499 ,   1867    ,   1269    ,   4293    ,   14633   ,0 };
            const std::uint32_t dim1172JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   15  ,   37  ,   29  ,   75  ,   191 ,   41  ,   11  ,   339 ,   485 ,   13635   ,0 };
            const std::uint32_t dim1173JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   27  ,   53  ,   13  ,   121 ,   209 ,   411 ,   51  ,   1003    ,   6587    ,   8247    ,0 };
            const std::uint32_t dim1174JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   13  ,   7   ,   43  ,   155 ,   467 ,   491 ,   1181    ,   1105    ,   2165    ,   16347   ,0 };
            const std::uint32_t dim1175JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   21  ,   19  ,   89  ,   25  ,   353 ,   223 ,   1063    ,   111 ,   611 ,   2225    ,0 };
            const std::uint32_t dim1176JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   3   ,   41  ,   95  ,   183 ,   135 ,   919 ,   861 ,   2929    ,   7189    ,   5505    ,0 };
            const std::uint32_t dim1177JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   13  ,   39  ,   85  ,   135 ,   403 ,   39  ,   1893    ,   3667    ,   2609    ,   9251    ,0 };
            const std::uint32_t dim1178JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   25  ,   5   ,   1   ,   179 ,   491 ,   953 ,   393 ,   2005    ,   1401    ,   12589   ,0 };
            const std::uint32_t dim1179JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   25  ,   19  ,   25  ,   73  ,   63  ,   897 ,   701 ,   345 ,   4995    ,   2411    ,0 };
            const std::uint32_t dim1180JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   31  ,   15  ,   121 ,   161 ,   127 ,   847 ,   1547    ,   3379    ,   4763    ,   8349    ,0 };
            const std::uint32_t dim1181JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   25  ,   61  ,   87  ,   235 ,   117 ,   861 ,   977 ,   2979    ,   3333    ,   10911   ,0 };
            const std::uint32_t dim1182JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   5   ,   57  ,   33  ,   129 ,   295 ,   225 ,   1497    ,   2367    ,   5379    ,   12721   ,0 };
            const std::uint32_t dim1183JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   19  ,   43  ,   43  ,   217 ,   139 ,   637 ,   567 ,   3661    ,   2807    ,   11061   ,0 };
            const std::uint32_t dim1184JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   27  ,   41  ,   97  ,   89  ,   53  ,   375 ,   1871    ,   2575    ,   1545    ,   455 ,0 };
            const std::uint32_t dim1185JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   13  ,   15  ,   77  ,   229 ,   329 ,   663 ,   1943    ,   1411    ,   5755    ,   16279   ,0 };
            const std::uint32_t dim1186JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   1   ,   3   ,   65  ,   21  ,   239 ,   619 ,   1801    ,   233 ,   3441    ,   12777   ,0 };
            const std::uint32_t dim1187JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   9   ,   63  ,   9   ,   19  ,   65  ,   759 ,   1871    ,   3537    ,   4453    ,   15443   ,0 };
            const std::uint32_t dim1188JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   17  ,   35  ,   43  ,   199 ,   167 ,   507 ,   669 ,   3593    ,   1645    ,   11791   ,0 };
            const std::uint32_t dim1189JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   25  ,   21  ,   111 ,   171 ,   349 ,   423 ,   1793    ,   659 ,   5211    ,   3547    ,0 };
            const std::uint32_t dim1190JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   23  ,   53  ,   95  ,   81  ,   383 ,   639 ,   1113    ,   2021    ,   7897    ,   4803    ,0 };
            const std::uint32_t dim1191JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   19  ,   63  ,   61  ,   165 ,   3   ,   565 ,   829 ,   3071    ,   6605    ,   3625    ,0 };
            const std::uint32_t dim1192JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   13  ,   53  ,   89  ,   97  ,   307 ,   555 ,   2039    ,   2753    ,   169 ,   941 ,0 };
            const std::uint32_t dim1193JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   9   ,   41  ,   45  ,   89  ,   155 ,   269 ,   51  ,   3791    ,   5563    ,   4757    ,0 };
            const std::uint32_t dim1194JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   23  ,   35  ,   19  ,   93  ,   205 ,   51  ,   375 ,   2107    ,   6357    ,   16257   ,0 };
            const std::uint32_t dim1195JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   3   ,   45  ,   107 ,   141 ,   315 ,   107 ,   219 ,   51  ,   7629    ,   6865    ,0 };
            const std::uint32_t dim1196JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   19  ,   23  ,   17  ,   77  ,   409 ,   59  ,   1649    ,   4029    ,   6541    ,   1075    ,0 };
            const std::uint32_t dim1197JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   1   ,   37  ,   13  ,   221 ,   277 ,   61  ,   1509    ,   1713    ,   4597    ,   5907    ,0 };
            const std::uint32_t dim1198JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   19  ,   53  ,   109 ,   123 ,   243 ,   1001    ,   291 ,   2265    ,   45  ,   437 ,0 };
            const std::uint32_t dim1199JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   17  ,   63  ,   65  ,   67  ,   359 ,   139 ,   699 ,   3037    ,   6123    ,   11885   ,0 };
            const std::uint32_t dim1200JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   3   ,   45  ,   125 ,   107 ,   75  ,   631 ,   769 ,   1431    ,   2089    ,   4919    ,0 };
            const std::uint32_t dim1201JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   27  ,   31  ,   63  ,   75  ,   265 ,   727 ,   1197    ,   3549    ,   7677    ,   10831   ,0 };
            const std::uint32_t dim1202JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   17  ,   61  ,   67  ,   169 ,   325 ,   627 ,   489 ,   729 ,   3585    ,   14253   ,0 };
            const std::uint32_t dim1203JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   1   ,   39  ,   23  ,   11  ,   23  ,   3   ,   973 ,   2161    ,   5613    ,   5711    ,0 };
            const std::uint32_t dim1204JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   3   ,   33  ,   31  ,   139 ,   275 ,   391 ,   1625    ,   2037    ,   389 ,   3853    ,0 };
            const std::uint32_t dim1205JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   17  ,   47  ,   19  ,   171 ,   219 ,   959 ,   1623    ,   1069    ,   1833    ,   4467    ,0 };
            const std::uint32_t dim1206JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   3   ,   29  ,   59  ,   159 ,   385 ,   183 ,   1091    ,   491 ,   8087    ,   4047    ,0 };
            const std::uint32_t dim1207JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   19  ,   3   ,   121 ,   29  ,   97  ,   345 ,   1573    ,   2993    ,   7987    ,   5397    ,0 };
            const std::uint32_t dim1208JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   31  ,   9   ,   57  ,   33  ,   489 ,   389 ,   1065    ,   2715    ,   5955    ,   11267   ,0 };
            const std::uint32_t dim1209JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   25  ,   7   ,   67  ,   245 ,   159 ,   987 ,   1297    ,   277 ,   2223    ,   9865    ,0 };
            const std::uint32_t dim1210JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   5   ,   11  ,   109 ,   171 ,   181 ,   303 ,   1875    ,   1915    ,   5007    ,   15563   ,0 };
            const std::uint32_t dim1211JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   21  ,   7   ,   67  ,   155 ,   503 ,   751 ,   1721    ,   3405    ,   4717    ,   12567   ,0 };
            const std::uint32_t dim1212JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   1   ,   51  ,   67  ,   57  ,   373 ,   835 ,   911 ,   3899    ,   7235    ,   5943    ,0 };
            const std::uint32_t dim1213JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   21  ,   63  ,   21  ,   209 ,   321 ,   75  ,   551 ,   2741    ,   535 ,   14693   ,0 };
            const std::uint32_t dim1214JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   21  ,   53  ,   23  ,   189 ,   463 ,   707 ,   637 ,   4055    ,   851 ,   12377   ,0 };
            const std::uint32_t dim1215JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   13  ,   39  ,   17  ,   7   ,   487 ,   731 ,   1965    ,   2395    ,   5129    ,   6677    ,0 };
            const std::uint32_t dim1216JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   5   ,   57  ,   15  ,   247 ,   325 ,   789 ,   1771    ,   2811    ,   6453    ,   7031    ,0 };
            const std::uint32_t dim1217JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   21  ,   21  ,   27  ,   113 ,   345 ,   999 ,   7   ,   3241    ,   2569    ,   9175    ,0 };
            const std::uint32_t dim1218JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   19  ,   41  ,   51  ,   37  ,   409 ,   553 ,   693 ,   1877    ,   4015    ,   1749    ,0 };
            const std::uint32_t dim1219JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   3   ,   7   ,   11  ,   197 ,   5   ,   601 ,   451 ,   2117    ,   4519    ,   5913    ,0 };
            const std::uint32_t dim1220JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   11  ,   53  ,   81  ,   187 ,   169 ,   419 ,   175 ,   2041    ,   2537    ,   16333   ,0 };
            const std::uint32_t dim1221JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   1   ,   9   ,   117 ,   33  ,   233 ,   581 ,   1575    ,   2131    ,   2065    ,   6597    ,0 };
            const std::uint32_t dim1222JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   27  ,   7   ,   111 ,   51  ,   311 ,   297 ,   1773    ,   193 ,   5599    ,   271 ,0 };
            const std::uint32_t dim1223JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   17  ,   49  ,   85  ,   247 ,   7   ,   1005    ,   1191    ,   399 ,   7775    ,   5635    ,0 };
            const std::uint32_t dim1224JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   31  ,   23  ,   9   ,   251 ,   97  ,   835 ,   813 ,   1335    ,   7955    ,   3977    ,0 };
            const std::uint32_t dim1225JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   3   ,   39  ,   5   ,   19  ,   111 ,   523 ,   1475    ,   2169    ,   4121    ,   1171    ,0 };
            const std::uint32_t dim1226JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   3   ,   19  ,   73  ,   43  ,   45  ,   57  ,   165 ,   3659    ,   7585    ,   8549    ,0 };
            const std::uint32_t dim1227JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   25  ,   57  ,   117 ,   15  ,   289 ,   953 ,   1123    ,   2327    ,   7957    ,   6043    ,0 };
            const std::uint32_t dim1228JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   7   ,   45  ,   63  ,   39  ,   349 ,   871 ,   1215    ,   2915    ,   1061    ,   7633    ,0 };
            const std::uint32_t dim1229JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   1   ,   33  ,   55  ,   213 ,   245 ,   221 ,   259 ,   1679    ,   1507    ,   14275   ,0 };
            const std::uint32_t dim1230JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   5   ,   15  ,   59  ,   55  ,   349 ,   121 ,   1471    ,   2119    ,   2559    ,   6379    ,0 };
            const std::uint32_t dim1231JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   7   ,   23  ,   125 ,   137 ,   171 ,   775 ,   1069    ,   605 ,   2945    ,   16089   ,0 };
            const std::uint32_t dim1232JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   9   ,   9   ,   43  ,   131 ,   385 ,   527 ,   757 ,   1263    ,   5285    ,   16309   ,0 };
            const std::uint32_t dim1233JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   3   ,   39  ,   5   ,   163 ,   459 ,   697 ,   715 ,   3827    ,   3295    ,   9163    ,0 };
            const std::uint32_t dim1234JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   7   ,   29  ,   7   ,   177 ,   207 ,   465 ,   59  ,   1485    ,   7731    ,   9843    ,0 };
            const std::uint32_t dim1235JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   21  ,   57  ,   87  ,   191 ,   399 ,   689 ,   935 ,   2771    ,   1025    ,   715 ,0 };
            const std::uint32_t dim1236JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   29  ,   19  ,   107 ,   253 ,   155 ,   163 ,   659 ,   3711    ,   2127    ,   10465   ,0 };
            const std::uint32_t dim1237JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   7   ,   43  ,   27  ,   211 ,   407 ,   153 ,   1939    ,   3243    ,   6655    ,   15983   ,0 };
            const std::uint32_t dim1238JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   27  ,   21  ,   23  ,   63  ,   271 ,   515 ,   261 ,   1947    ,   6257    ,   12861   ,0 };
            const std::uint32_t dim1239JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   19  ,   57  ,   67  ,   221 ,   179 ,   725 ,   1179    ,   3983    ,   1585    ,   5899    ,0 };
            const std::uint32_t dim1240JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   7   ,   61  ,   97  ,   131 ,   145 ,   637 ,   733 ,   2533    ,   1993    ,   14399   ,0 };
            const std::uint32_t dim1241JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   13  ,   39  ,   83  ,   247 ,   235 ,   621 ,   1557    ,   3075    ,   3165    ,   16027   ,0 };
            const std::uint32_t dim1242JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   9   ,   11  ,   111 ,   153 ,   437 ,   687 ,   1845    ,   3547    ,   2097    ,   2219    ,0 };
            const std::uint32_t dim1243JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   21  ,   13  ,   43  ,   33  ,   51  ,   1021    ,   1883    ,   1261    ,   2823    ,   12771   ,0 };
            const std::uint32_t dim1244JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   3   ,   35  ,   19  ,   127 ,   419 ,   203 ,   1869    ,   1477    ,   5239    ,   6113    ,0 };
            const std::uint32_t dim1245JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   31  ,   63  ,   75  ,   185 ,   507 ,   401 ,   1079    ,   67  ,   1621    ,   2849    ,0 };
            const std::uint32_t dim1246JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   31  ,   61  ,   125 ,   77  ,   169 ,   51  ,   1115    ,   1625    ,   3533    ,   5953    ,0 };
            const std::uint32_t dim1247JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   29  ,   51  ,   23  ,   43  ,   505 ,   313 ,   887 ,   551 ,   4401    ,   2133    ,0 };
            const std::uint32_t dim1248JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   11  ,   37  ,   55  ,   161 ,   353 ,   347 ,   1991    ,   4009    ,   2073    ,   12169   ,0 };
            const std::uint32_t dim1249JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   29  ,   51  ,   15  ,   13  ,   391 ,   677 ,   225 ,   1467    ,   6615    ,   1895    ,0 };
            const std::uint32_t dim1250JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   29  ,   15  ,   93  ,   103 ,   147 ,   323 ,   837 ,   1983    ,   1613    ,   10667   ,0 };
            const std::uint32_t dim1251JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   21  ,   11  ,   39  ,   95  ,   473 ,   591 ,   1645    ,   67  ,   2793    ,   11217   ,0 };
            const std::uint32_t dim1252JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   9   ,   51  ,   1   ,   243 ,   445 ,   583 ,   375 ,   2289    ,   4911    ,   10511   ,0 };
            const std::uint32_t dim1253JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   23  ,   15  ,   111 ,   239 ,   247 ,   511 ,   1723    ,   2911    ,   2627    ,   10549   ,0 };
            const std::uint32_t dim1254JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   15  ,   37  ,   31  ,   135 ,   347 ,   599 ,   765 ,   2561    ,   4635    ,   10659   ,0 };
            const std::uint32_t dim1255JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   9   ,   49  ,   93  ,   187 ,   415 ,   247 ,   1871    ,   617 ,   6711    ,   3283    ,0 };
            const std::uint32_t dim1256JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   25  ,   25  ,   37  ,   97  ,   365 ,   477 ,   1383    ,   1357    ,   693 ,   14743   ,0 };
            const std::uint32_t dim1257JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   25  ,   19  ,   109 ,   99  ,   471 ,   661 ,   1633    ,   3773    ,   921 ,   4113    ,0 };
            const std::uint32_t dim1258JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   13  ,   61  ,   21  ,   255 ,   161 ,   233 ,   1181    ,   3003    ,   1465    ,   9299    ,0 };
            const std::uint32_t dim1259JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   7   ,   59  ,   53  ,   129 ,   127 ,   961 ,   893 ,   499 ,   5265    ,   2299    ,0 };
            const std::uint32_t dim1260JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   29  ,   45  ,   85  ,   173 ,   131 ,   775 ,   1527    ,   1899    ,   4833    ,   12763   ,0 };
            const std::uint32_t dim1261JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   1   ,   1   ,   115 ,   245 ,   205 ,   609 ,   1729    ,   915 ,   5965    ,   11001   ,0 };
            const std::uint32_t dim1262JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   3   ,   61  ,   91  ,   93  ,   363 ,   457 ,   1497    ,   2539    ,   553 ,   7581    ,0 };
            const std::uint32_t dim1263JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   29  ,   5   ,   7   ,   171 ,   393 ,   381 ,   935 ,   3467    ,   6199    ,   6625    ,0 };
            const std::uint32_t dim1264JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   15  ,   25  ,   65  ,   137 ,   349 ,   61  ,   1035    ,   591 ,   4317    ,   13949   ,0 };
            const std::uint32_t dim1265JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   27  ,   17  ,   87  ,   233 ,   227 ,   341 ,   639 ,   1813    ,   871 ,   12871   ,0 };
            const std::uint32_t dim1266JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   29  ,   15  ,   31  ,   81  ,   61  ,   857 ,   1305    ,   3631    ,   2919    ,   2093    ,0 };
            const std::uint32_t dim1267JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   27  ,   5   ,   49  ,   1   ,   49  ,   745 ,   543 ,   847 ,   2469    ,   3513    ,0 };
            const std::uint32_t dim1268JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   15  ,   39  ,   47  ,   73  ,   33  ,   469 ,   1809    ,   2105    ,   7995    ,   11285   ,0 };
            const std::uint32_t dim1269JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   9   ,   9   ,   81  ,   211 ,   295 ,   791 ,   1267    ,   2945    ,   5639    ,   6967    ,0 };
            const std::uint32_t dim1270JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   13  ,   11  ,   43  ,   221 ,   161 ,   263 ,   905 ,   2767    ,   4491    ,   7605    ,0 };
            const std::uint32_t dim1271JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   13  ,   9   ,   91  ,   123 ,   449 ,   21  ,   941 ,   1391    ,   3469    ,   16027   ,0 };
            const std::uint32_t dim1272JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   5   ,   13  ,   77  ,   69  ,   245 ,   905 ,   231 ,   547 ,   2933    ,   4307    ,0 };
            const std::uint32_t dim1273JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   25  ,   59  ,   49  ,   49  ,   183 ,   213 ,   29  ,   1801    ,   6271    ,   16283   ,0 };
            const std::uint32_t dim1274JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   3   ,   15  ,   35  ,   157 ,   87  ,   453 ,   1939    ,   2697    ,   3325    ,   8679    ,0 };
            const std::uint32_t dim1275JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   7   ,   45  ,   77  ,   73  ,   203 ,   321 ,   425 ,   581 ,   481 ,   15367   ,0 };
            const std::uint32_t dim1276JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   11  ,   51  ,   11  ,   59  ,   355 ,   677 ,   1565    ,   123 ,   2403    ,   12835   ,0 };
            const std::uint32_t dim1277JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   7   ,   27  ,   17  ,   81  ,   295 ,   131 ,   955 ,   4065    ,   797 ,   16165   ,0 };
            const std::uint32_t dim1278JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   29  ,   63  ,   51  ,   215 ,   269 ,   1013    ,   517 ,   1857    ,   141 ,   4495    ,0 };
            const std::uint32_t dim1279JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   17  ,   47  ,   121 ,   199 ,   177 ,   1023    ,   1009    ,   3535    ,   4825    ,   16349   ,0 };
            const std::uint32_t dim1280JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   21  ,   25  ,   107 ,   165 ,   43  ,   213 ,   1847    ,   1945    ,   3463    ,   2259    ,0 };
            const std::uint32_t dim1281JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   5   ,   5   ,   5   ,   65  ,   493 ,   725 ,   755 ,   111 ,   6673    ,   213 ,0 };
            const std::uint32_t dim1282JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   3   ,   29  ,   17  ,   87  ,   207 ,   793 ,   873 ,   2341    ,   3505    ,   5751    ,0 };
            const std::uint32_t dim1283JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   27  ,   47  ,   123 ,   157 ,   427 ,   273 ,   139 ,   4043    ,   4083    ,   14121   ,0 };
            const std::uint32_t dim1284JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   25  ,   17  ,   41  ,   245 ,   441 ,   47  ,   1   ,   2393    ,   405 ,   4021    ,0 };
            const std::uint32_t dim1285JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   31  ,   9   ,   115 ,   165 ,   93  ,   701 ,   255 ,   895 ,   995 ,   12371   ,0 };
            const std::uint32_t dim1286JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   23  ,   13  ,   9   ,   141 ,   31  ,   973 ,   441 ,   3335    ,   2567    ,   6993    ,0 };
            const std::uint32_t dim1287JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   19  ,   25  ,   61  ,   139 ,   39  ,   987 ,   385 ,   2199    ,   7675    ,   13301   ,0 };
            const std::uint32_t dim1288JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   1   ,   35  ,   121 ,   187 ,   273 ,   905 ,   245 ,   1031    ,   6203    ,   8165    ,0 };
            const std::uint32_t dim1289JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   31  ,   59  ,   97  ,   45  ,   25  ,   803 ,   1245    ,   2659    ,   7471    ,   8367    ,0 };
            const std::uint32_t dim1290JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   21  ,   41  ,   47  ,   183 ,   419 ,   279 ,   1901    ,   1081    ,   3575    ,   8591    ,0 };
            const std::uint32_t dim1291JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   11  ,   39  ,   119 ,   245 ,   403 ,   703 ,   1547    ,   743 ,   7957    ,   15123   ,0 };
            const std::uint32_t dim1292JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   11  ,   31  ,   71  ,   55  ,   3   ,   961 ,   991 ,   1665    ,   5539    ,   8187    ,0 };
            const std::uint32_t dim1293JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   19  ,   7   ,   1   ,   35  ,   463 ,   1003    ,   555 ,   669 ,   2119    ,   10939   ,0 };
            const std::uint32_t dim1294JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   17  ,   29  ,   99  ,   133 ,   107 ,   907 ,   7   ,   3047    ,   1263    ,   7497    ,0 };
            const std::uint32_t dim1295JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   1   ,   53  ,   39  ,   191 ,   201 ,   189 ,   465 ,   453 ,   1967    ,   1033    ,0 };
            const std::uint32_t dim1296JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   25  ,   19  ,   5   ,   155 ,   105 ,   923 ,   2045    ,   2889    ,   7685    ,   13847   ,0 };
            const std::uint32_t dim1297JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   7   ,   61  ,   93  ,   41  ,   183 ,   783 ,   2011    ,   2967    ,   2949    ,   10247   ,0 };
            const std::uint32_t dim1298JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   3   ,   53  ,   105 ,   63  ,   9   ,   131 ,   897 ,   347 ,   7683    ,   16027   ,0 };
            const std::uint32_t dim1299JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   19  ,   37  ,   37  ,   143 ,   37  ,   493 ,   533 ,   733 ,   2295    ,   4203    ,0 };
            const std::uint32_t dim1300JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   15  ,   23  ,   83  ,   185 ,   495 ,   1023    ,   1473    ,   1501    ,   373 ,   201 ,0 };
            const std::uint32_t dim1301JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   31  ,   51  ,   115 ,   233 ,   289 ,   201 ,   869 ,   3177    ,   4649    ,   16111   ,0 };
            const std::uint32_t dim1302JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   23  ,   7   ,   59  ,   233 ,   447 ,   781 ,   1249    ,   71  ,   5857    ,   15481   ,0 };
            const std::uint32_t dim1303JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   31  ,   1   ,   67  ,   243 ,   129 ,   737 ,   1443    ,   3647    ,   2391    ,   3635    ,0 };
            const std::uint32_t dim1304JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   17  ,   39  ,   117 ,   81  ,   395 ,   119 ,   413 ,   1295    ,   7889    ,   13569   ,0 };
            const std::uint32_t dim1305JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   29  ,   5   ,   123 ,   89  ,   143 ,   779 ,   1173    ,   3211    ,   3027    ,   10145   ,0 };
            const std::uint32_t dim1306JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   19  ,   53  ,   39  ,   199 ,   487 ,   797 ,   123 ,   871 ,   6335    ,   7957    ,0 };
            const std::uint32_t dim1307JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   13  ,   11  ,   105 ,   121 ,   403 ,   283 ,   413 ,   1957    ,   6557    ,   8429    ,0 };
            const std::uint32_t dim1308JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   23  ,   21  ,   109 ,   37  ,   463 ,   613 ,   927 ,   1857    ,   7003    ,   3477    ,0 };
            const std::uint32_t dim1309JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   15  ,   37  ,   81  ,   27  ,   259 ,   661 ,   287 ,   615 ,   6151    ,   13759   ,0 };
            const std::uint32_t dim1310JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   27  ,   59  ,   85  ,   223 ,   499 ,   571 ,   1853    ,   1419    ,   7761    ,   8385    ,0 };
            const std::uint32_t dim1311JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   23  ,   57  ,   53  ,   163 ,   437 ,   657 ,   851 ,   3177    ,   6477    ,   13003   ,0 };
            const std::uint32_t dim1312JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   3   ,   7   ,   37  ,   167 ,   49  ,   595 ,   1493    ,   369 ,   687 ,   13463   ,0 };
            const std::uint32_t dim1313JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   27  ,   63  ,   49  ,   157 ,   379 ,   779 ,   99  ,   3457    ,   4477    ,   6531    ,0 };
            const std::uint32_t dim1314JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   5   ,   55  ,   77  ,   159 ,   371 ,   369 ,   743 ,   3571    ,   1877    ,   14767   ,0 };
            const std::uint32_t dim1315JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   25  ,   11  ,   65  ,   187 ,   253 ,   437 ,   1301    ,   2871    ,   6219    ,   817 ,0 };
            const std::uint32_t dim1316JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   23  ,   33  ,   25  ,   49  ,   491 ,   315 ,   11  ,   2163    ,   6155    ,   23  ,0 };
            const std::uint32_t dim1317JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   27  ,   31  ,   81  ,   7   ,   355 ,   289 ,   1481    ,   2969    ,   1067    ,   7399    ,0 };
            const std::uint32_t dim1318JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   1   ,   57  ,   39  ,   201 ,   271 ,   223 ,   1117    ,   727 ,   7491    ,   4043    ,0 };
            const std::uint32_t dim1319JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   9   ,   57  ,   17  ,   161 ,   221 ,   385 ,   2027    ,   1195    ,   2489    ,   12377   ,0 };
            const std::uint32_t dim1320JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   27  ,   59  ,   101 ,   27  ,   177 ,   1005    ,   63  ,   3029    ,   7345    ,   14429   ,0 };
            const std::uint32_t dim1321JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   17  ,   5   ,   111 ,   239 ,   85  ,   57  ,   1625    ,   657 ,   5931    ,   4929    ,0 };
            const std::uint32_t dim1322JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   7   ,   41  ,   29  ,   9   ,   73  ,   875 ,   1665    ,   325 ,   27  ,   997 ,0 };
            const std::uint32_t dim1323JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   21  ,   61  ,   119 ,   247 ,   307 ,   1011    ,   1489    ,   2361    ,   5781    ,   2465    ,0 };
            const std::uint32_t dim1324JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   1   ,   21  ,   105 ,   77  ,   57  ,   983 ,   1519    ,   3543    ,   5025    ,   14051   ,0 };
            const std::uint32_t dim1325JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   13  ,   39  ,   113 ,   69  ,   81  ,   155 ,   101 ,   427 ,   733 ,   10085   ,0 };
            const std::uint32_t dim1326JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   1   ,   25  ,   109 ,   109 ,   303 ,   323 ,   565 ,   2267    ,   2755    ,   9165    ,0 };
            const std::uint32_t dim1327JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   15  ,   43  ,   103 ,   163 ,   265 ,   849 ,   1969    ,   2247    ,   4495    ,   7301    ,0 };
            const std::uint32_t dim1328JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   23  ,   9   ,   81  ,   103 ,   193 ,   845 ,   1603    ,   2493    ,   4919    ,   10649   ,0 };
            const std::uint32_t dim1329JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   9   ,   23  ,   91  ,   33  ,   115 ,   599 ,   1755    ,   53  ,   1757    ,   145 ,0 };
            const std::uint32_t dim1330JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   1   ,   39  ,   5   ,   233 ,   399 ,   187 ,   943 ,   2325    ,   437 ,   4421    ,0 };
            const std::uint32_t dim1331JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   11  ,   39  ,   29  ,   131 ,   363 ,   885 ,   1921    ,   3703    ,   4197    ,   9703    ,0 };
            const std::uint32_t dim1332JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   21  ,   43  ,   27  ,   151 ,   193 ,   211 ,   1229    ,   4031    ,   681 ,   5103    ,0 };
            const std::uint32_t dim1333JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   19  ,   23  ,   41  ,   47  ,   315 ,   169 ,   271 ,   1877    ,   6357    ,   7709    ,0 };
            const std::uint32_t dim1334JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   11  ,   27  ,   123 ,   33  ,   287 ,   293 ,   335 ,   2331    ,   141 ,   10095   ,0 };
            const std::uint32_t dim1335JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   15  ,   33  ,   93  ,   123 ,   277 ,   833 ,   115 ,   3799    ,   1519    ,   153 ,0 };
            const std::uint32_t dim1336JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   11  ,   3   ,   97  ,   225 ,   179 ,   601 ,   687 ,   253 ,   2839    ,   10985   ,0 };
            const std::uint32_t dim1337JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   11  ,   51  ,   5   ,   141 ,   487 ,   325 ,   1691    ,   1291    ,   4677    ,   9087    ,0 };
            const std::uint32_t dim1338JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   5   ,   11  ,   99  ,   195 ,   459 ,   171 ,   361 ,   1621    ,   5377    ,   4651    ,0 };
            const std::uint32_t dim1339JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   29  ,   47  ,   5   ,   29  ,   107 ,   751 ,   739 ,   2815    ,   3709    ,   15493   ,0 };
            const std::uint32_t dim1340JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   3   ,   63  ,   47  ,   15  ,   433 ,   501 ,   1687    ,   2035    ,   6263    ,   12681   ,0 };
            const std::uint32_t dim1341JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   1   ,   57  ,   91  ,   33  ,   217 ,   141 ,   2005    ,   2405    ,   1987    ,   14957   ,0 };
            const std::uint32_t dim1342JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   25  ,   23  ,   93  ,   37  ,   129 ,   747 ,   1607    ,   849 ,   2119    ,   11855   ,0 };
            const std::uint32_t dim1343JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   15  ,   55  ,   55  ,   125 ,   235 ,   455 ,   2027    ,   1709    ,   7217    ,   10341   ,0 };
            const std::uint32_t dim1344JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   1   ,   3   ,   69  ,   167 ,   373 ,   87  ,   901 ,   2333    ,   6751    ,   5809    ,0 };
            const std::uint32_t dim1345JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   19  ,   25  ,   67  ,   197 ,   395 ,   735 ,   941 ,   1753    ,   3923    ,   8805    ,0 };
            const std::uint32_t dim1346JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   17  ,   29  ,   1   ,   205 ,   511 ,   179 ,   1191    ,   17  ,   3179    ,   6891    ,0 };
            const std::uint32_t dim1347JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   9   ,   31  ,   99  ,   133 ,   253 ,   239 ,   1729    ,   4093    ,   5759    ,   15357   ,0 };
            const std::uint32_t dim1348JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   31  ,   35  ,   125 ,   167 ,   417 ,   431 ,   709 ,   415 ,   1093    ,   11361   ,0 };
            const std::uint32_t dim1349JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   7   ,   59  ,   57  ,   89  ,   119 ,   537 ,   1157    ,   2539    ,   5783    ,   15093   ,0 };
            const std::uint32_t dim1350JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   17  ,   41  ,   105 ,   33  ,   301 ,   601 ,   537 ,   3877    ,   797 ,   1319    ,0 };
            const std::uint32_t dim1351JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   3   ,   59  ,   79  ,   47  ,   191 ,   985 ,   83  ,   3535    ,   4135    ,   16165   ,0 };
            const std::uint32_t dim1352JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   13  ,   61  ,   35  ,   193 ,   141 ,   961 ,   1733    ,   4051    ,   2657    ,   9183    ,0 };
            const std::uint32_t dim1353JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   25  ,   49  ,   127 ,   233 ,   291 ,   445 ,   1639    ,   4023    ,   4791    ,   279 ,0 };
            const std::uint32_t dim1354JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   15  ,   39  ,   91  ,   81  ,   433 ,   7   ,   1897    ,   2659    ,   7877    ,   15733   ,0 };
            const std::uint32_t dim1355JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   19  ,   5   ,   125 ,   181 ,   305 ,   377 ,   1699    ,   2157    ,   4617    ,   7165    ,0 };
            const std::uint32_t dim1356JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   11  ,   27  ,   19  ,   217 ,   171 ,   343 ,   61  ,   3799    ,   4923    ,   14279   ,0 };
            const std::uint32_t dim1357JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   13  ,   41  ,   19  ,   19  ,   359 ,   101 ,   1795    ,   127 ,   7067    ,   4327    ,0 };
            const std::uint32_t dim1358JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   15  ,   5   ,   43  ,   47  ,   103 ,   549 ,   767 ,   2695    ,   1689    ,   5569    ,0 };
            const std::uint32_t dim1359JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   7   ,   33  ,   35  ,   105 ,   283 ,   957 ,   1255    ,   2085    ,   6263    ,   4537    ,0 };
            const std::uint32_t dim1360JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   27  ,   23  ,   49  ,   169 ,   455 ,   163 ,   301 ,   3107    ,   6859    ,   14477   ,0 };
            const std::uint32_t dim1361JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   13  ,   11  ,   25  ,   231 ,   171 ,   173 ,   661 ,   1921    ,   3535    ,   10157   ,0 };
            const std::uint32_t dim1362JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   27  ,   19  ,   23  ,   97  ,   409 ,   347 ,   1413    ,   2273    ,   7305    ,   12597   ,0 };
            const std::uint32_t dim1363JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   11  ,   63  ,   49  ,   247 ,   459 ,   195 ,   1579    ,   539 ,   6283    ,   14829   ,0 };
            const std::uint32_t dim1364JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   19  ,   37  ,   105 ,   31  ,   87  ,   413 ,   511 ,   271 ,   6265    ,   9499    ,0 };
            const std::uint32_t dim1365JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   23  ,   39  ,   97  ,   239 ,   397 ,   975 ,   1369    ,   2397    ,   409 ,   3495    ,0 };
            const std::uint32_t dim1366JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   25  ,   45  ,   11  ,   81  ,   233 ,   299 ,   1269    ,   1129    ,   1679    ,   10195   ,0 };
            const std::uint32_t dim1367JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   13  ,   29  ,   3   ,   189 ,   231 ,   535 ,   1201    ,   1215    ,   1889    ,   6169    ,0 };
            const std::uint32_t dim1368JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   31  ,   53  ,   17  ,   197 ,   453 ,   13  ,   181 ,   2663    ,   3869    ,   7269    ,0 };
            const std::uint32_t dim1369JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   27  ,   37  ,   71  ,   89  ,   505 ,   769 ,   1359    ,   295 ,   6061    ,   8363    ,0 };
            const std::uint32_t dim1370JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   9   ,   1   ,   111 ,   157 ,   89  ,   777 ,   1713    ,   117 ,   285 ,   6353    ,0 };
            const std::uint32_t dim1371JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   29  ,   53  ,   57  ,   3   ,   225 ,   885 ,   1445    ,   3673    ,   7857    ,   3843    ,0 };
            const std::uint32_t dim1372JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   29  ,   23  ,   43  ,   19  ,   175 ,   573 ,   1709    ,   2303    ,   5607    ,   4347    ,0 };
            const std::uint32_t dim1373JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   19  ,   41  ,   93  ,   13  ,   3   ,   483 ,   1365    ,   411 ,   5147    ,   10505   ,0 };
            const std::uint32_t dim1374JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   3   ,   17  ,   51  ,   23  ,   19  ,   411 ,   741 ,   877 ,   7121    ,   7639    ,0 };
            const std::uint32_t dim1375JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   7   ,   45  ,   103 ,   69  ,   387 ,   803 ,   29  ,   1469    ,   2139    ,   6397    ,0 };
            const std::uint32_t dim1376JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   11  ,   43  ,   5   ,   19  ,   441 ,   285 ,   1657    ,   2133    ,   6343    ,   11817   ,0 };
            const std::uint32_t dim1377JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   31  ,   31  ,   19  ,   15  ,   475 ,   131 ,   1687    ,   1647    ,   4685    ,   1135    ,0 };
            const std::uint32_t dim1378JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   17  ,   59  ,   125 ,   127 ,   63  ,   451 ,   949 ,   4041    ,   6649    ,   12187   ,0 };
            const std::uint32_t dim1379JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   25  ,   13  ,   59  ,   159 ,   107 ,   509 ,   787 ,   2517    ,   6679    ,   2809    ,0 };
            const std::uint32_t dim1380JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   17  ,   5   ,   87  ,   235 ,   379 ,   599 ,   1971    ,   969 ,   853 ,   10481   ,0 };
            const std::uint32_t dim1381JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   7   ,   35  ,   47  ,   113 ,   349 ,   451 ,   1827    ,   2647    ,   367 ,   2581    ,0 };
            const std::uint32_t dim1382JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   1   ,   39  ,   29  ,   45  ,   365 ,   317 ,   129 ,   137 ,   5975    ,   3353    ,0 };
            const std::uint32_t dim1383JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   17  ,   3   ,   5   ,   61  ,   11  ,   587 ,   769 ,   2127    ,   2625    ,   12545   ,0 };
            const std::uint32_t dim1384JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   21  ,   1   ,   127 ,   235 ,   343 ,   807 ,   147 ,   3517    ,   3471    ,   4625    ,0 };
            const std::uint32_t dim1385JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   31  ,   23  ,   81  ,   23  ,   171 ,   403 ,   1083    ,   4049    ,   1959    ,   16307   ,0 };
            const std::uint32_t dim1386JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   21  ,   37  ,   99  ,   83  ,   33  ,   705 ,   369 ,   2445    ,   3253    ,   16171   ,0 };
            const std::uint32_t dim1387JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   17  ,   61  ,   121 ,   75  ,   89  ,   823 ,   1519    ,   1997    ,   6433    ,   5013    ,0 };
            const std::uint32_t dim1388JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   7   ,   47  ,   7   ,   71  ,   475 ,   517 ,   1271    ,   3815    ,   5969    ,   607 ,0 };
            const std::uint32_t dim1389JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   13  ,   15  ,   37  ,   89  ,   43  ,   489 ,   1853    ,   1195    ,   3097    ,   10297   ,0 };
            const std::uint32_t dim1390JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   25  ,   39  ,   95  ,   43  ,   145 ,   231 ,   1859    ,   3201    ,   1377    ,   7091    ,0 };
            const std::uint32_t dim1391JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   13  ,   43  ,   117 ,   111 ,   231 ,   101 ,   1801    ,   739 ,   945 ,   15585   ,0 };
            const std::uint32_t dim1392JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   23  ,   3   ,   35  ,   167 ,   485 ,   951 ,   1729    ,   1831    ,   2639    ,   6561    ,0 };
            const std::uint32_t dim1393JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   5   ,   31  ,   103 ,   85  ,   111 ,   545 ,   789 ,   945 ,   2691    ,   327 ,0 };
            const std::uint32_t dim1394JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   29  ,   61  ,   127 ,   59  ,   137 ,   485 ,   1673    ,   3295    ,   4185    ,   6489    ,0 };
            const std::uint32_t dim1395JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   31  ,   9   ,   115 ,   11  ,   73  ,   267 ,   195 ,   1445    ,   873 ,   7285    ,0 };
            const std::uint32_t dim1396JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   3   ,   19  ,   9   ,   71  ,   287 ,   89  ,   329 ,   953 ,   2237    ,   16341   ,0 };
            const std::uint32_t dim1397JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   19  ,   31  ,   5   ,   49  ,   293 ,   65  ,   291 ,   93  ,   2553    ,   8407    ,0 };
            const std::uint32_t dim1398JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   17  ,   13  ,   15  ,   111 ,   211 ,   935 ,   1165    ,   2975    ,   339 ,   16333   ,0 };
            const std::uint32_t dim1399JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   17  ,   57  ,   9   ,   63  ,   243 ,   431 ,   289 ,   3493    ,   2879    ,   4801    ,0 };
            const std::uint32_t dim1400JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   17  ,   15  ,   53  ,   191 ,   439 ,   981 ,   751 ,   4025    ,   7177    ,   4887    ,0 };
            const std::uint32_t dim1401JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   11  ,   61  ,   43  ,   103 ,   151 ,   33  ,   421 ,   1949    ,   5915    ,   5515    ,0 };
            const std::uint32_t dim1402JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   1   ,   55  ,   45  ,   227 ,   27  ,   491 ,   1479    ,   3323    ,   5485    ,   5493    ,0 };
            const std::uint32_t dim1403JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   9   ,   11  ,   1   ,   249 ,   113 ,   415 ,   295 ,   3437    ,   3877    ,   6675    ,0 };
            const std::uint32_t dim1404JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   9   ,   43  ,   127 ,   57  ,   115 ,   685 ,   165 ,   973 ,   2707    ,   2503    ,0 };
            const std::uint32_t dim1405JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   1   ,   29  ,   125 ,   45  ,   307 ,   625 ,   1477    ,   2565    ,   2949    ,   1729    ,0 };
            const std::uint32_t dim1406JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   23  ,   7   ,   45  ,   245 ,   301 ,   531 ,   1419    ,   1795    ,   5757    ,   15219   ,0 };
            const std::uint32_t dim1407JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   15  ,   49  ,   71  ,   109 ,   145 ,   79  ,   1333    ,   1589    ,   3851    ,   2879    ,0 };
            const std::uint32_t dim1408JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   11  ,   15  ,   37  ,   239 ,   217 ,   193 ,   1687    ,   1721    ,   8059    ,   9027    ,0 };
            const std::uint32_t dim1409JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   13  ,   49  ,   57  ,   189 ,   433 ,   569 ,   1285    ,   1891    ,   6079    ,   13469   ,0 };
            const std::uint32_t dim1410JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   19  ,   61  ,   27  ,   181 ,   365 ,   121 ,   883 ,   1611    ,   1521    ,   11437   ,0 };
            const std::uint32_t dim1411JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   17  ,   37  ,   71  ,   71  ,   495 ,   519 ,   879 ,   2993    ,   6275    ,   14345   ,0 };
            const std::uint32_t dim1412JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   29  ,   5   ,   121 ,   29  ,   293 ,   745 ,   1839    ,   2061    ,   2721    ,   11741   ,0 };
            const std::uint32_t dim1413JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   23  ,   61  ,   55  ,   99  ,   409 ,   211 ,   783 ,   1841    ,   193 ,   1941    ,0 };
            const std::uint32_t dim1414JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   11  ,   49  ,   87  ,   81  ,   225 ,   211 ,   1263    ,   1403    ,   6169    ,   6235    ,0 };
            const std::uint32_t dim1415JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   11  ,   35  ,   71  ,   145 ,   417 ,   485 ,   1565    ,   2101    ,   4153    ,   5239    ,0 };
            const std::uint32_t dim1416JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   13  ,   41  ,   45  ,   79  ,   157 ,   477 ,   677 ,   3961    ,   1127    ,   1139    ,0 };
            const std::uint32_t dim1417JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   27  ,   39  ,   23  ,   197 ,   123 ,   431 ,   273 ,   2723    ,   1303    ,   13271   ,0 };
            const std::uint32_t dim1418JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   13  ,   21  ,   59  ,   109 ,   267 ,   173 ,   997 ,   2701    ,   3719    ,   3703    ,0 };
            const std::uint32_t dim1419JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   1   ,   5   ,   57  ,   181 ,   241 ,   1   ,   1063    ,   199 ,   8181    ,   12721   ,0 };
            const std::uint32_t dim1420JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   15  ,   61  ,   107 ,   231 ,   65  ,   933 ,   677 ,   3883    ,   2621    ,   8821    ,0 };
            const std::uint32_t dim1421JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   9   ,   33  ,   41  ,   55  ,   503 ,   683 ,   747 ,   3619    ,   7885    ,   851 ,0 };
            const std::uint32_t dim1422JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   9   ,   25  ,   27  ,   123 ,   97  ,   731 ,   583 ,   2535    ,   1267    ,   5921    ,0 };
            const std::uint32_t dim1423JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   27  ,   63  ,   69  ,   99  ,   475 ,   709 ,   1239    ,   861 ,   1229    ,   11369   ,0 };
            const std::uint32_t dim1424JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   17  ,   47  ,   123 ,   159 ,   57  ,   871 ,   465 ,   783 ,   4093    ,   15277   ,0 };
            const std::uint32_t dim1425JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   17  ,   47  ,   89  ,   139 ,   301 ,   45  ,   627 ,   4073    ,   3187    ,   9633    ,0 };
            const std::uint32_t dim1426JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   21  ,   43  ,   19  ,   25  ,   457 ,   879 ,   113 ,   847 ,   201 ,   15683   ,0 };
            const std::uint32_t dim1427JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   9   ,   47  ,   43  ,   215 ,   407 ,   979 ,   51  ,   635 ,   467 ,   6365    ,0 };
            const std::uint32_t dim1428JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   7   ,   11  ,   53  ,   5   ,   471 ,   317 ,   1719    ,   755 ,   5211    ,   7599    ,0 };
            const std::uint32_t dim1429JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   11  ,   43  ,   67  ,   203 ,   15  ,   75  ,   1063    ,   1763    ,   3537    ,   13511   ,0 };
            const std::uint32_t dim1430JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   17  ,   37  ,   91  ,   55  ,   95  ,   843 ,   751 ,   3501    ,   6203    ,   2999    ,0 };
            const std::uint32_t dim1431JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   19  ,   61  ,   37  ,   157 ,   309 ,   361 ,   1499    ,   1845    ,   3675    ,   6221    ,0 };
            const std::uint32_t dim1432JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   15  ,   9   ,   25  ,   123 ,   25  ,   525 ,   227 ,   3429    ,   1573    ,   12321   ,0 };
            const std::uint32_t dim1433JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   9   ,   17  ,   91  ,   61  ,   263 ,   129 ,   1853    ,   1911    ,   5065    ,   775 ,0 };
            const std::uint32_t dim1434JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   31  ,   15  ,   3   ,   207 ,   505 ,   123 ,   477 ,   1285    ,   7007    ,   2873    ,0 };
            const std::uint32_t dim1435JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   7   ,   15  ,   123 ,   249 ,   467 ,   229 ,   845 ,   1913    ,   461 ,   6235    ,0 };
            const std::uint32_t dim1436JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   15  ,   9   ,   121 ,   211 ,   231 ,   491 ,   521 ,   3621    ,   7285    ,   3165    ,0 };
            const std::uint32_t dim1437JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   21  ,   43  ,   1   ,   35  ,   339 ,   671 ,   719 ,   1739    ,   501 ,   9573    ,0 };
            const std::uint32_t dim1438JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   13  ,   37  ,   81  ,   1   ,   281 ,   785 ,   831 ,   991 ,   7485    ,   15619   ,0 };
            const std::uint32_t dim1439JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   29  ,   47  ,   29  ,   99  ,   311 ,   519 ,   545 ,   1115    ,   6651    ,   793 ,0 };
            const std::uint32_t dim1440JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   17  ,   15  ,   17  ,   65  ,   101 ,   411 ,   231 ,   2959    ,   8077    ,   673 ,0 };
            const std::uint32_t dim1441JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   27  ,   47  ,   127 ,   237 ,   319 ,   293 ,   1109    ,   3863    ,   213 ,   2149    ,0 };
            const std::uint32_t dim1442JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   11  ,   61  ,   27  ,   129 ,   57  ,   743 ,   889 ,   3707    ,   469 ,   11949   ,0 };
            const std::uint32_t dim1443JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   23  ,   13  ,   119 ,   125 ,   75  ,   753 ,   1951    ,   1181    ,   291 ,   11737   ,0 };
            const std::uint32_t dim1444JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   31  ,   19  ,   43  ,   113 ,   309 ,   721 ,   175 ,   1041    ,   7123    ,   103 ,0 };
            const std::uint32_t dim1445JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   21  ,   19  ,   71  ,   175 ,   309 ,   9   ,   807 ,   961 ,   6741    ,   5075    ,0 };
            const std::uint32_t dim1446JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   15  ,   27  ,   83  ,   207 ,   67  ,   71  ,   289 ,   2901    ,   7637    ,   9525    ,0 };
            const std::uint32_t dim1447JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   21  ,   9   ,   19  ,   67  ,   401 ,   165 ,   1297    ,   3159    ,   2881    ,   15979   ,0 };
            const std::uint32_t dim1448JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   11  ,   21  ,   27  ,   33  ,   95  ,   853 ,   1699    ,   875 ,   6519    ,   9109    ,0 };
            const std::uint32_t dim1449JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   31  ,   5   ,   123 ,   215 ,   165 ,   405 ,   623 ,   845 ,   4149    ,   5015    ,0 };
            const std::uint32_t dim1450JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   31  ,   13  ,   23  ,   55  ,   129 ,   789 ,   803 ,   2077    ,   1885    ,   1669    ,0 };
            const std::uint32_t dim1451JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   31  ,   39  ,   93  ,   7   ,   485 ,   571 ,   417 ,   3839    ,   1289    ,   4127    ,0 };
            const std::uint32_t dim1452JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   23  ,   63  ,   123 ,   249 ,   75  ,   515 ,   2009    ,   949 ,   3291    ,   727 ,0 };
            const std::uint32_t dim1453JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   21  ,   15  ,   57  ,   235 ,   25  ,   507 ,   1055    ,   3161    ,   4351    ,   8855    ,0 };
            const std::uint32_t dim1454JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   23  ,   39  ,   71  ,   151 ,   377 ,   469 ,   665 ,   1197    ,   3503    ,   655 ,0 };
            const std::uint32_t dim1455JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   5   ,   35  ,   67  ,   203 ,   33  ,   319 ,   925 ,   1021    ,   6869    ,   5145    ,0 };
            const std::uint32_t dim1456JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   21  ,   61  ,   119 ,   195 ,   383 ,   573 ,   135 ,   2371    ,   1665    ,   4957    ,0 };
            const std::uint32_t dim1457JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   7   ,   47  ,   93  ,   201 ,   269 ,   329 ,   209 ,   1659    ,   1547    ,   4605    ,0 };
            const std::uint32_t dim1458JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   9   ,   47  ,   71  ,   13  ,   451 ,   51  ,   1073    ,   3691    ,   6881    ,   14801   ,0 };
            const std::uint32_t dim1459JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   13  ,   33  ,   75  ,   155 ,   283 ,   599 ,   517 ,   2251    ,   6217    ,   10487   ,0 };
            const std::uint32_t dim1460JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   7   ,   49  ,   65  ,   235 ,   159 ,   733 ,   939 ,   283 ,   6935    ,   14367   ,0 };
            const std::uint32_t dim1461JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   7   ,   19  ,   71  ,   227 ,   307 ,   515 ,   1701    ,   747 ,   3475    ,   8165    ,0 };
            const std::uint32_t dim1462JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   13  ,   19  ,   1   ,   97  ,   425 ,   739 ,   451 ,   3789    ,   5337    ,   2023    ,0 };
            const std::uint32_t dim1463JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   7   ,   27  ,   23  ,   169 ,   137 ,   537 ,   61  ,   2207    ,   917 ,   1209    ,0 };
            const std::uint32_t dim1464JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   29  ,   5   ,   121 ,   197 ,   159 ,   467 ,   581 ,   1679    ,   6605    ,   1989    ,0 };
            const std::uint32_t dim1465JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   5   ,   33  ,   61  ,   77  ,   383 ,   977 ,   781 ,   175 ,   8151    ,   7979    ,0 };
            const std::uint32_t dim1466JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   1   ,   1   ,   3   ,   95  ,   193 ,   453 ,   649 ,   1137    ,   485 ,   14345   ,0 };
            const std::uint32_t dim1467JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   1   ,   13  ,   41  ,   159 ,   327 ,   105 ,   1569    ,   475 ,   1295    ,   3767    ,0 };
            const std::uint32_t dim1468JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   25  ,   7   ,   73  ,   235 ,   271 ,   491 ,   1385    ,   2567    ,   1463    ,   12731   ,0 };
            const std::uint32_t dim1469JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   9   ,   9   ,   37  ,   199 ,   249 ,   9   ,   299 ,   3891    ,   2373    ,   11553   ,0 };
            const std::uint32_t dim1470JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   19  ,   47  ,   81  ,   25  ,   125 ,   933 ,   1637    ,   469 ,   6351    ,   4219    ,0 };
            const std::uint32_t dim1471JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   31  ,   5   ,   67  ,   13  ,   63  ,   615 ,   1089    ,   2291    ,   3105    ,   7009    ,0 };
            const std::uint32_t dim1472JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   1   ,   43  ,   49  ,   141 ,   189 ,   1015    ,   1527    ,   1511    ,   3093    ,   5497    ,0 };
            const std::uint32_t dim1473JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   3   ,   51  ,   121 ,   89  ,   161 ,   517 ,   467 ,   2837    ,   2275    ,   4987    ,0 };
            const std::uint32_t dim1474JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   9   ,   63  ,   31  ,   109 ,   331 ,   607 ,   1271    ,   3639    ,   617 ,   13177   ,0 };
            const std::uint32_t dim1475JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   9   ,   25  ,   73  ,   237 ,   145 ,   885 ,   1945    ,   1871    ,   5401    ,   15403   ,0 };
            const std::uint32_t dim1476JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   1   ,   63  ,   29  ,   145 ,   377 ,   429 ,   1663    ,   1643    ,   2713    ,   6621    ,0 };
            const std::uint32_t dim1477JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   29  ,   7   ,   87  ,   53  ,   129 ,   503 ,   961 ,   3535    ,   3255    ,   7621    ,0 };
            const std::uint32_t dim1478JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   5   ,   47  ,   13  ,   243 ,   155 ,   863 ,   103 ,   1699    ,   5063    ,   8221    ,0 };
            const std::uint32_t dim1479JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   31  ,   61  ,   1   ,   253 ,   67  ,   369 ,   521 ,   3429    ,   6935    ,   3383    ,0 };
            const std::uint32_t dim1480JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   11  ,   61  ,   11  ,   187 ,   145 ,   7   ,   535 ,   831 ,   933 ,   7779    ,0 };
            const std::uint32_t dim1481JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   25  ,   33  ,   117 ,   161 ,   169 ,   33  ,   1415    ,   1493    ,   1599    ,   1109    ,0 };
            const std::uint32_t dim1482JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   29  ,   19  ,   75  ,   143 ,   467 ,   785 ,   455 ,   2593    ,   7539    ,   6283    ,0 };
            const std::uint32_t dim1483JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   11  ,   5   ,   19  ,   187 ,   357 ,   955 ,   631 ,   3697    ,   4641    ,   14353   ,0 };
            const std::uint32_t dim1484JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   3   ,   21  ,   25  ,   79  ,   375 ,   611 ,   915 ,   2491    ,   5691    ,   773 ,0 };
            const std::uint32_t dim1485JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   29  ,   23  ,   7   ,   27  ,   207 ,   157 ,   1021    ,   2411    ,   5061    ,   7493    ,0 };
            const std::uint32_t dim1486JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   13  ,   7   ,   7   ,   159 ,   393 ,   51  ,   1573    ,   1353    ,   2373    ,   12721   ,0 };
            const std::uint32_t dim1487JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   5   ,   55  ,   43  ,   7   ,   411 ,   353 ,   379 ,   2213    ,   6257    ,   5825    ,0 };
            const std::uint32_t dim1488JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   5   ,   37  ,   65  ,   69  ,   251 ,   893 ,   1747    ,   4065    ,   3937    ,   1855    ,0 };
            const std::uint32_t dim1489JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   3   ,   11  ,   97  ,   111 ,   509 ,   569 ,   839 ,   2431    ,   3475    ,   12283   ,0 };
            const std::uint32_t dim1490JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   13  ,   63  ,   85  ,   193 ,   351 ,   491 ,   205 ,   1051    ,   403 ,   1749    ,0 };
            const std::uint32_t dim1491JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   27  ,   61  ,   61  ,   169 ,   189 ,   549 ,   1589    ,   3567    ,   7301    ,   12723   ,0 };
            const std::uint32_t dim1492JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   13  ,   39  ,   121 ,   75  ,   261 ,   919 ,   1557    ,   635 ,   2123    ,   3771    ,0 };
            const std::uint32_t dim1493JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   7   ,   39  ,   107 ,   109 ,   165 ,   91  ,   1049    ,   3897    ,   1395    ,   9573    ,0 };
            const std::uint32_t dim1494JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   19  ,   9   ,   61  ,   209 ,   205 ,   363 ,   823 ,   2445    ,   7301    ,   7141    ,0 };
            const std::uint32_t dim1495JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   5   ,   31  ,   13  ,   61  ,   153 ,   847 ,   67  ,   2227    ,   4119    ,   9231    ,0 };
            const std::uint32_t dim1496JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   13  ,   63  ,   93  ,   199 ,   437 ,   319 ,   735 ,   2015    ,   1719    ,   3253    ,0 };
            const std::uint32_t dim1497JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   31  ,   19  ,   27  ,   141 ,   357 ,   647 ,   895 ,   345 ,   5937    ,   15711   ,0 };
            const std::uint32_t dim1498JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   15  ,   35  ,   73  ,   69  ,   205 ,   545 ,   387 ,   3487    ,   7391    ,   3337    ,0 };
            const std::uint32_t dim1499JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   27  ,   55  ,   51  ,   179 ,   125 ,   1013    ,   35  ,   2741    ,   7793    ,   4347    ,0 };
            const std::uint32_t dim1500JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   31  ,   57  ,   55  ,   3   ,   385 ,   421 ,   1543    ,   2809    ,   1887    ,   13709   ,0 };
            const std::uint32_t dim1501JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   29  ,   23  ,   115 ,   25  ,   295 ,   267 ,   101 ,   3005    ,   2601    ,   4959    ,0 };
            const std::uint32_t dim1502JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   27  ,   11  ,   11  ,   35  ,   257 ,   23  ,   2013    ,   1369    ,   6503    ,   2589    ,0 };
            const std::uint32_t dim1503JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   5   ,   43  ,   101 ,   87  ,   231 ,   761 ,   1991    ,   3167    ,   5689    ,   9565    ,0 };
            const std::uint32_t dim1504JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   17  ,   37  ,   65  ,   249 ,   119 ,   727 ,   793 ,   929 ,   6275    ,   12173   ,0 };
            const std::uint32_t dim1505JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   1   ,   11  ,   93  ,   27  ,   291 ,   411 ,   1069    ,   1283    ,   7593    ,   4335    ,0 };
            const std::uint32_t dim1506JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   23  ,   45  ,   51  ,   93  ,   401 ,   515 ,   749 ,   1293    ,   8155    ,   15123   ,0 };
            const std::uint32_t dim1507JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   21  ,   17  ,   67  ,   69  ,   371 ,   507 ,   143 ,   2393    ,   6267    ,   7143    ,0 };
            const std::uint32_t dim1508JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   1   ,   5   ,   79  ,   75  ,   361 ,   689 ,   339 ,   1855    ,   6863    ,   15841   ,0 };
            const std::uint32_t dim1509JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   23  ,   3   ,   43  ,   57  ,   233 ,   927 ,   1095    ,   1827    ,   401 ,   825 ,0 };
            const std::uint32_t dim1510JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   31  ,   7   ,   67  ,   201 ,   27  ,   699 ,   535 ,   3073    ,   6895    ,   3021    ,0 };
            const std::uint32_t dim1511JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   1   ,   19  ,   13  ,   83  ,   221 ,   727 ,   745 ,   2131    ,   3757    ,   1493    ,0 };
            const std::uint32_t dim1512JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   13  ,   29  ,   101 ,   255 ,   243 ,   763 ,   535 ,   169 ,   1987    ,   4071    ,0 };
            const std::uint32_t dim1513JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   21  ,   33  ,   117 ,   213 ,   143 ,   351 ,   1735    ,   1651    ,   5781    ,   8803    ,0 };
            const std::uint32_t dim1514JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   17  ,   39  ,   57  ,   209 ,   141 ,   865 ,   1731    ,   3349    ,   7107    ,   15983   ,0 };
            const std::uint32_t dim1515JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   21  ,   33  ,   117 ,   201 ,   481 ,   711 ,   1207    ,   1971    ,   3353    ,   5827    ,0 };
            const std::uint32_t dim1516JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   13  ,   1   ,   121 ,   115 ,   449 ,   801 ,   1507    ,   2323    ,   6709    ,   5533    ,0 };
            const std::uint32_t dim1517JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   5   ,   5   ,   35  ,   81  ,   469 ,   691 ,   443 ,   501 ,   6745    ,   421 ,0 };
            const std::uint32_t dim1518JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   27  ,   41  ,   83  ,   39  ,   349 ,   585 ,   551 ,   643 ,   6659    ,   61  ,0 };
            const std::uint32_t dim1519JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   25  ,   41  ,   45  ,   203 ,   89  ,   305 ,   1433    ,   1879    ,   6703    ,   14323   ,0 };
            const std::uint32_t dim1520JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   27  ,   37  ,   97  ,   117 ,   431 ,   197 ,   807 ,   1841    ,   8075    ,   4613    ,0 };
            const std::uint32_t dim1521JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   23  ,   47  ,   69  ,   129 ,   451 ,   113 ,   1397    ,   3005    ,   7599    ,   101 ,0 };
            const std::uint32_t dim1522JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   11  ,   47  ,   117 ,   181 ,   85  ,   545 ,   571 ,   3227    ,   4097    ,   7937    ,0 };
            const std::uint32_t dim1523JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   27  ,   53  ,   11  ,   181 ,   177 ,   121 ,   363 ,   2751    ,   4799    ,   14215   ,0 };
            const std::uint32_t dim1524JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   27  ,   15  ,   101 ,   229 ,   411 ,   947 ,   189 ,   119 ,   6707    ,   5177    ,0 };
            const std::uint32_t dim1525JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   29  ,   39  ,   65  ,   149 ,   185 ,   915 ,   889 ,   1651    ,   5977    ,   273 ,0 };
            const std::uint32_t dim1526JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   7   ,   45  ,   113 ,   203 ,   459 ,   747 ,   1577    ,   2247    ,   5005    ,   2375    ,0 };
            const std::uint32_t dim1527JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   9   ,   5   ,   63  ,   83  ,   193 ,   363 ,   257 ,   4075    ,   7497    ,   4579    ,0 };
            const std::uint32_t dim1528JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   1   ,   55  ,   107 ,   161 ,   471 ,   245 ,   1303    ,   1821    ,   3395    ,   8957    ,0 };
            const std::uint32_t dim1529JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   5   ,   17  ,   83  ,   215 ,   467 ,   489 ,   827 ,   1951    ,   3753    ,   13333   ,0 };
            const std::uint32_t dim1530JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   27  ,   31  ,   89  ,   55  ,   445 ,   489 ,   1171    ,   107 ,   1479    ,   1389    ,0 };
            const std::uint32_t dim1531JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   21  ,   23  ,   51  ,   21  ,   129 ,   349 ,   195 ,   2177    ,   529 ,   5479    ,0 };
            const std::uint32_t dim1532JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   15  ,   31  ,   99  ,   169 ,   299 ,   21  ,   1379    ,   3845    ,   4991    ,   8755    ,0 };
            const std::uint32_t dim1533JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   23  ,   29  ,   47  ,   219 ,   289 ,   559 ,   393 ,   793 ,   3217    ,   12103   ,0 };
            const std::uint32_t dim1534JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   5   ,   13  ,   107 ,   119 ,   159 ,   421 ,   243 ,   3231    ,   5331    ,   14511   ,0 };
            const std::uint32_t dim1535JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   13  ,   9   ,   1   ,   99  ,   7   ,   743 ,   1125    ,   2969    ,   1205    ,   2963    ,0 };
            const std::uint32_t dim1536JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   5   ,   1   ,   25  ,   101 ,   397 ,   75  ,   141 ,   3503    ,   3003    ,   11363   ,0 };
            const std::uint32_t dim1537JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   21  ,   25  ,   55  ,   7   ,   189 ,   599 ,   1071    ,   343 ,   2877    ,   5131    ,0 };
            const std::uint32_t dim1538JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   13  ,   25  ,   113 ,   175 ,   31  ,   265 ,   1901    ,   1779    ,   1787    ,   14551   ,0 };
            const std::uint32_t dim1539JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   31  ,   53  ,   69  ,   49  ,   281 ,   57  ,   1865    ,   3211    ,   5545    ,   12597   ,0 };
            const std::uint32_t dim1540JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   3   ,   51  ,   99  ,   23  ,   303 ,   455 ,   2021    ,   2903    ,   2521    ,   10211   ,0 };
            const std::uint32_t dim1541JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   17  ,   49  ,   55  ,   147 ,   177 ,   515 ,   1333    ,   3357    ,   6483    ,   4599    ,0 };
            const std::uint32_t dim1542JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   31  ,   3   ,   1   ,   15  ,   263 ,   1007    ,   1377    ,   1245    ,   313 ,   10227   ,0 };
            const std::uint32_t dim1543JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   21  ,   7   ,   61  ,   201 ,   95  ,   407 ,   661 ,   2159    ,   3255    ,   5749    ,0 };
            const std::uint32_t dim1544JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   13  ,   31  ,   65  ,   135 ,   117 ,   737 ,   1165    ,   2305    ,   5347    ,   2739    ,0 };
            const std::uint32_t dim1545JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   25  ,   49  ,   63  ,   115 ,   65  ,   693 ,   1211    ,   763 ,   6949    ,   11655   ,0 };
            const std::uint32_t dim1546JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   13  ,   37  ,   15  ,   61  ,   175 ,   377 ,   765 ,   269 ,   1363    ,   8199    ,0 };
            const std::uint32_t dim1547JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   27  ,   27  ,   113 ,   131 ,   207 ,   921 ,   1051    ,   2205    ,   1197    ,   16233   ,0 };
            const std::uint32_t dim1548JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   5   ,   19  ,   115 ,   95  ,   93  ,   87  ,   1379    ,   3295    ,   5211    ,   9113    ,0 };
            const std::uint32_t dim1549JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   21  ,   19  ,   9   ,   39  ,   101 ,   5   ,   1903    ,   1067    ,   2845    ,   2025    ,0 };
            const std::uint32_t dim1550JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   31  ,   5   ,   39  ,   23  ,   505 ,   563 ,   1445    ,   1177    ,   1485    ,   13551   ,0 };
            const std::uint32_t dim1551JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   31  ,   57  ,   107 ,   241 ,   361 ,   353 ,   699 ,   171 ,   5211    ,   2235    ,0 };
            const std::uint32_t dim1552JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   15  ,   7   ,   115 ,   119 ,   157 ,   293 ,   827 ,   3249    ,   3463    ,   11873   ,0 };
            const std::uint32_t dim1553JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   11  ,   15  ,   17  ,   195 ,   257 ,   31  ,   1207    ,   549 ,   7807    ,   14135   ,0 };
            const std::uint32_t dim1554JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   25  ,   59  ,   37  ,   205 ,   507 ,   855 ,   303 ,   683 ,   4277    ,   9387    ,0 };
            const std::uint32_t dim1555JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   25  ,   1   ,   121 ,   29  ,   485 ,   707 ,   319 ,   3717    ,   2741    ,   5241    ,0 };
            const std::uint32_t dim1556JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   15  ,   55  ,   107 ,   227 ,   129 ,   1011    ,   319 ,   713 ,   5263    ,   7865    ,0 };
            const std::uint32_t dim1557JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   17  ,   11  ,   7   ,   107 ,   21  ,   349 ,   1101    ,   3279    ,   5541    ,   12485   ,0 };
            const std::uint32_t dim1558JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   25  ,   9   ,   45  ,   149 ,   187 ,   229 ,   671 ,   1219    ,   5171    ,   2073    ,0 };
            const std::uint32_t dim1559JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   17  ,   49  ,   23  ,   7   ,   219 ,   639 ,   1497    ,   3103    ,   3047    ,   7723    ,0 };
            const std::uint32_t dim1560JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   13  ,   5   ,   3   ,   249 ,   429 ,   289 ,   625 ,   325 ,   1257    ,   16251   ,0 };
            const std::uint32_t dim1561JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   17  ,   21  ,   31  ,   11  ,   189 ,   73  ,   583 ,   2843    ,   1873    ,   1215    ,0 };
            const std::uint32_t dim1562JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   25  ,   61  ,   123 ,   251 ,   485 ,   543 ,   1851    ,   2827    ,   397 ,   7313    ,0 };
            const std::uint32_t dim1563JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   29  ,   59  ,   103 ,   159 ,   295 ,   227 ,   1127    ,   1905    ,   4121    ,   3233    ,0 };
            const std::uint32_t dim1564JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   17  ,   55  ,   7   ,   1   ,   381 ,   33  ,   39  ,   485 ,   3967    ,   4401    ,0 };
            const std::uint32_t dim1565JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   5   ,   29  ,   7   ,   95  ,   191 ,   23  ,   1205    ,   2427    ,   5439    ,   12585   ,0 };
            const std::uint32_t dim1566JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   27  ,   9   ,   73  ,   195 ,   225 ,   597 ,   683 ,   3335    ,   6341    ,   10527   ,0 };
            const std::uint32_t dim1567JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   13  ,   15  ,   83  ,   41  ,   241 ,   833 ,   1253    ,   3389    ,   2927    ,   2629    ,0 };
            const std::uint32_t dim1568JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   25  ,   55  ,   23  ,   249 ,   151 ,   123 ,   667 ,   3835    ,   2215    ,   6189    ,0 };
            const std::uint32_t dim1569JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   31  ,   43  ,   91  ,   181 ,   509 ,   453 ,   171 ,   2883    ,   1247    ,   5105    ,0 };
            const std::uint32_t dim1570JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   3   ,   17  ,   59  ,   127 ,   173 ,   343 ,   901 ,   3419    ,   4755    ,   12367   ,0 };
            const std::uint32_t dim1571JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   15  ,   49  ,   119 ,   1   ,   183 ,   1021    ,   561 ,   2405    ,   4093    ,   963 ,0 };
            const std::uint32_t dim1572JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   21  ,   61  ,   63  ,   119 ,   11  ,   695 ,   1591    ,   2175    ,   5143    ,   10491   ,0 };
            const std::uint32_t dim1573JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   27  ,   23  ,   91  ,   131 ,   23  ,   891 ,   1033    ,   1341    ,   1747    ,   12085   ,0 };
            const std::uint32_t dim1574JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   11  ,   1   ,   35  ,   189 ,   131 ,   617 ,   417 ,   3347    ,   3995    ,   11723   ,0 };
            const std::uint32_t dim1575JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   31  ,   35  ,   113 ,   83  ,   27  ,   399 ,   1615    ,   47  ,   1455    ,   4163    ,0 };
            const std::uint32_t dim1576JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   29  ,   61  ,   103 ,   105 ,   495 ,   495 ,   1751    ,   2035    ,   7827    ,   11193   ,0 };
            const std::uint32_t dim1577JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   29  ,   35  ,   125 ,   193 ,   59  ,   15  ,   1319    ,   1169    ,   3789    ,   2003    ,0 };
            const std::uint32_t dim1578JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   27  ,   9   ,   33  ,   197 ,   65  ,   191 ,   783 ,   3685    ,   7505    ,   13407   ,0 };
            const std::uint32_t dim1579JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   1   ,   35  ,   97  ,   55  ,   259 ,   477 ,   1835    ,   3083    ,   7879    ,   4701    ,0 };
            const std::uint32_t dim1580JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   5   ,   31  ,   5   ,   125 ,   393 ,   317 ,   1577    ,   3741    ,   3823    ,   12447   ,0 };
            const std::uint32_t dim1581JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   9   ,   59  ,   81  ,   85  ,   233 ,   465 ,   239 ,   1525    ,   3095    ,   5793    ,0 };
            const std::uint32_t dim1582JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   9   ,   49  ,   49  ,   239 ,   81  ,   475 ,   799 ,   2999    ,   2985    ,   11587   ,0 };
            const std::uint32_t dim1583JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   27  ,   55  ,   43  ,   149 ,   191 ,   325 ,   2035    ,   1645    ,   2153    ,   13237   ,0 };
            const std::uint32_t dim1584JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   27  ,   59  ,   5   ,   49  ,   277 ,   75  ,   1759    ,   2753    ,   95  ,   2959    ,0 };
            const std::uint32_t dim1585JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   21  ,   57  ,   119 ,   35  ,   457 ,   137 ,   1877    ,   2613    ,   4209    ,   9669    ,0 };
            const std::uint32_t dim1586JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   25  ,   21  ,   51  ,   65  ,   155 ,   37  ,   783 ,   3427    ,   2763    ,   14361   ,0 };
            const std::uint32_t dim1587JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   23  ,   11  ,   53  ,   181 ,   267 ,   285 ,   1927    ,   3591    ,   3735    ,   11471   ,0 };
            const std::uint32_t dim1588JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   5   ,   25  ,   51  ,   31  ,   201 ,   851 ,   871 ,   3665    ,   193 ,   10929   ,0 };
            const std::uint32_t dim1589JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   1   ,   25  ,   35  ,   133 ,   459 ,   45  ,   525 ,   3171    ,   1123    ,   5679    ,0 };
            const std::uint32_t dim1590JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   29  ,   47  ,   123 ,   75  ,   101 ,   89  ,   1949    ,   1801    ,   3859    ,   6557    ,0 };
            const std::uint32_t dim1591JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   25  ,   1   ,   93  ,   205 ,   447 ,   865 ,   1309    ,   3009    ,   945 ,   6961    ,0 };
            const std::uint32_t dim1592JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   21  ,   47  ,   91  ,   9   ,   23  ,   607 ,   1905    ,   2291    ,   5315    ,   6673    ,0 };
            const std::uint32_t dim1593JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   3   ,   33  ,   83  ,   27  ,   491 ,   467 ,   1819    ,   3295    ,   1589    ,   4771    ,0 };
            const std::uint32_t dim1594JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   17  ,   57  ,   73  ,   49  ,   69  ,   821 ,   1773    ,   459 ,   7945    ,   14471   ,0 };
            const std::uint32_t dim1595JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   19  ,   29  ,   9   ,   181 ,   311 ,   353 ,   2045    ,   2873    ,   7417    ,   15243   ,0 };
            const std::uint32_t dim1596JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   29  ,   45  ,   43  ,   17  ,   237 ,   915 ,   1069    ,   1429    ,   5629    ,   4501    ,0 };
            const std::uint32_t dim1597JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   9   ,   53  ,   57  ,   55  ,   275 ,   233 ,   1697    ,   2857    ,   919 ,   4507    ,0 };
            const std::uint32_t dim1598JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   17  ,   45  ,   81  ,   101 ,   209 ,   769 ,   783 ,   1949    ,   5933    ,   137 ,0 };
            const std::uint32_t dim1599JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   1   ,   33  ,   17  ,   87  ,   35  ,   927 ,   1595    ,   2443    ,   285 ,   12821   ,0 };
            const std::uint32_t dim1600JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   3   ,   33  ,   113 ,   243 ,   51  ,   203 ,   1683    ,   389 ,   2789    ,   9255    ,0 };
            const std::uint32_t dim1601JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   9   ,   1   ,   7   ,   227 ,   27  ,   773 ,   621 ,   3743    ,   6591    ,   407 ,0 };
            const std::uint32_t dim1602JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   29  ,   51  ,   113 ,   99  ,   305 ,   267 ,   907 ,   3861    ,   5335    ,   10851   ,0 };
            const std::uint32_t dim1603JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   27  ,   63  ,   65  ,   249 ,   87  ,   105 ,   2023    ,   1383    ,   4267    ,   8995    ,0 };
            const std::uint32_t dim1604JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   15  ,   11  ,   77  ,   9   ,   365 ,   711 ,   1367    ,   2101    ,   5833    ,   9799    ,0 };
            const std::uint32_t dim1605JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   7   ,   29  ,   13  ,   157 ,   259 ,   455 ,   389 ,   3177    ,   4243    ,   7615    ,0 };
            const std::uint32_t dim1606JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   25  ,   27  ,   31  ,   91  ,   195 ,   109 ,   1767    ,   987 ,   2715    ,   7613    ,0 };
            const std::uint32_t dim1607JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   23  ,   51  ,   89  ,   127 ,   485 ,   361 ,   1555    ,   441 ,   4963    ,   3371    ,0 };
            const std::uint32_t dim1608JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   27  ,   31  ,   25  ,   249 ,   35  ,   115 ,   1021    ,   1051    ,   3449    ,   3395    ,0 };
            const std::uint32_t dim1609JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   17  ,   41  ,   117 ,   173 ,   491 ,   281 ,   885 ,   471 ,   6665    ,   10041   ,0 };
            const std::uint32_t dim1610JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   7   ,   53  ,   117 ,   117 ,   479 ,   449 ,   569 ,   4049    ,   2747    ,   12963   ,0 };
            const std::uint32_t dim1611JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   11  ,   13  ,   107 ,   171 ,   7   ,   547 ,   1635    ,   1697    ,   1005    ,   11137   ,0 };
            const std::uint32_t dim1612JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   17  ,   51  ,   109 ,   81  ,   111 ,   395 ,   349 ,   1467    ,   1399    ,   15545   ,0 };
            const std::uint32_t dim1613JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   13  ,   47  ,   79  ,   119 ,   31  ,   239 ,   41  ,   2043    ,   2849    ,   16079   ,0 };
            const std::uint32_t dim1614JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   17  ,   41  ,   95  ,   193 ,   511 ,   879 ,   1223    ,   3133    ,   1675    ,   3929    ,0 };
            const std::uint32_t dim1615JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   15  ,   55  ,   21  ,   143 ,   279 ,   11  ,   717 ,   3021    ,   6207    ,   4499    ,0 };
            const std::uint32_t dim1616JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   3   ,   25  ,   37  ,   91  ,   227 ,   619 ,   1873    ,   1991    ,   793 ,   10021   ,0 };
            const std::uint32_t dim1617JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   17  ,   39  ,   75  ,   191 ,   117 ,   997 ,   735 ,   3771    ,   4243    ,   2491    ,0 };
            const std::uint32_t dim1618JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   19  ,   9   ,   71  ,   89  ,   427 ,   791 ,   623 ,   903 ,   6685    ,   9029    ,0 };
            const std::uint32_t dim1619JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   13  ,   49  ,   13  ,   151 ,   389 ,   677 ,   727 ,   3135    ,   1029    ,   12669   ,0 };
            const std::uint32_t dim1620JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   27  ,   31  ,   119 ,   219 ,   491 ,   819 ,   755 ,   3529    ,   3071    ,   16095   ,0 };
            const std::uint32_t dim1621JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   1   ,   57  ,   127 ,   171 ,   481 ,   467 ,   1131    ,   1481    ,   2491    ,   2717    ,0 };
            const std::uint32_t dim1622JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   7   ,   25  ,   55  ,   87  ,   225 ,   363 ,   843 ,   3581    ,   2511    ,   6685    ,0 };
            const std::uint32_t dim1623JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   29  ,   21  ,   91  ,   251 ,   403 ,   1007    ,   307 ,   2869    ,   6033    ,   14169   ,0 };
            const std::uint32_t dim1624JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   31  ,   43  ,   77  ,   71  ,   101 ,   995 ,   625 ,   2763    ,   7537    ,   1213    ,0 };
            const std::uint32_t dim1625JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   9   ,   45  ,   11  ,   235 ,   59  ,   561 ,   547 ,   815 ,   6123    ,   8173    ,0 };
            const std::uint32_t dim1626JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   25  ,   19  ,   107 ,   47  ,   103 ,   467 ,   1889    ,   2021    ,   2861    ,   7617    ,0 };
            const std::uint32_t dim1627JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   9   ,   3   ,   11  ,   231 ,   217 ,   213 ,   1497    ,   3125    ,   7421    ,   6221    ,0 };
            const std::uint32_t dim1628JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   27  ,   57  ,   27  ,   9   ,   507 ,   191 ,   1297    ,   3307    ,   4687    ,   13299   ,0 };
            const std::uint32_t dim1629JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   25  ,   17  ,   109 ,   57  ,   231 ,   123 ,   1297    ,   77  ,   785 ,   13731   ,0 };
            const std::uint32_t dim1630JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   25  ,   5   ,   85  ,   177 ,   365 ,   301 ,   655 ,   1743    ,   2009    ,   7759    ,0 };
            const std::uint32_t dim1631JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   19  ,   29  ,   105 ,   57  ,   469 ,   735 ,   875 ,   3749    ,   619 ,   15569   ,0 };
            const std::uint32_t dim1632JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   19  ,   21  ,   105 ,   19  ,   83  ,   117 ,   1599    ,   655 ,   63  ,   12143   ,0 };
            const std::uint32_t dim1633JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   9   ,   35  ,   123 ,   195 ,   109 ,   321 ,   1713    ,   793 ,   8067    ,   6903    ,0 };
            const std::uint32_t dim1634JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   1   ,   41  ,   43  ,   41  ,   51  ,   711 ,   1713    ,   3063    ,   6427    ,   3577    ,0 };
            const std::uint32_t dim1635JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   17  ,   3   ,   95  ,   159 ,   23  ,   605 ,   1431    ,   1289    ,   2225    ,   1689    ,0 };
            const std::uint32_t dim1636JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   19  ,   3   ,   83  ,   61  ,   133 ,   707 ,   453 ,   2487    ,   551 ,   13605   ,0 };
            const std::uint32_t dim1637JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   31  ,   37  ,   51  ,   157 ,   51  ,   423 ,   2021    ,   1837    ,   1873    ,   2919    ,0 };
            const std::uint32_t dim1638JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   3   ,   17  ,   19  ,   19  ,   181 ,   961 ,   669 ,   47  ,   7513    ,   7551    ,0 };
            const std::uint32_t dim1639JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   9   ,   7   ,   61  ,   219 ,   347 ,   21  ,   467 ,   955 ,   3255    ,   275 ,0 };
            const std::uint32_t dim1640JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   31  ,   57  ,   51  ,   9   ,   49  ,   491 ,   119 ,   1155    ,   3641    ,   16095   ,0 };
            const std::uint32_t dim1641JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   15  ,   37  ,   93  ,   27  ,   205 ,   889 ,   1463    ,   1567    ,   453 ,   13757   ,0 };
            const std::uint32_t dim1642JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   27  ,   51  ,   43  ,   189 ,   357 ,   591 ,   1783    ,   549 ,   761 ,   8683    ,0 };
            const std::uint32_t dim1643JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   13  ,   27  ,   25  ,   67  ,   145 ,   471 ,   1589    ,   2395    ,   6625    ,   3837    ,0 };
            const std::uint32_t dim1644JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   25  ,   61  ,   111 ,   125 ,   475 ,   489 ,   15  ,   3835    ,   5077    ,   14487   ,0 };
            const std::uint32_t dim1645JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   15  ,   55  ,   35  ,   169 ,   267 ,   135 ,   383 ,   733 ,   6913    ,   14153   ,0 };
            const std::uint32_t dim1646JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   19  ,   55  ,   89  ,   61  ,   175 ,   467 ,   1243    ,   1431    ,   1743    ,   8641    ,0 };
            const std::uint32_t dim1647JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   19  ,   41  ,   13  ,   45  ,   503 ,   285 ,   1727    ,   587 ,   5073    ,   13053   ,0 };
            const std::uint32_t dim1648JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   11  ,   39  ,   93  ,   167 ,   385 ,   165 ,   881 ,   1037    ,   1471    ,   14527   ,0 };
            const std::uint32_t dim1649JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   15  ,   9   ,   7   ,   49  ,   163 ,   219 ,   955 ,   1083    ,   2723    ,   3749    ,   15415   ,0 };
            const std::uint32_t dim1650JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   7   ,   43  ,   67  ,   87  ,   375 ,   405 ,   1663    ,   1263    ,   1895    ,   2229    ,0 };
            const std::uint32_t dim1651JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   27  ,   47  ,   77  ,   147 ,   417 ,   843 ,   1829    ,   3451    ,   2973    ,   7313    ,0 };
            const std::uint32_t dim1652JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   3   ,   25  ,   69  ,   255 ,   413 ,   43  ,   837 ,   957 ,   261 ,   8663    ,0 };
            const std::uint32_t dim1653JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   29  ,   35  ,   9   ,   57  ,   421 ,   751 ,   593 ,   3745    ,   3203    ,   14179   ,0 };
            const std::uint32_t dim1654JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   13  ,   25  ,   109 ,   169 ,   331 ,   537 ,   69  ,   2089    ,   7263    ,   15133   ,0 };
            const std::uint32_t dim1655JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   21  ,   21  ,   21  ,   145 ,   223 ,   167 ,   1297    ,   3257    ,   7465    ,   1557    ,0 };
            const std::uint32_t dim1656JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   11  ,   7   ,   31  ,   205 ,   97  ,   737 ,   79  ,   4083    ,   5601    ,   8411    ,0 };
            const std::uint32_t dim1657JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   7   ,   39  ,   117 ,   203 ,   225 ,   801 ,   741 ,   1861    ,   8091    ,   3169    ,0 };
            const std::uint32_t dim1658JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   15  ,   49  ,   109 ,   171 ,   109 ,   845 ,   1757    ,   2687    ,   5643    ,   3967    ,0 };
            const std::uint32_t dim1659JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   7   ,   41  ,   93  ,   165 ,   127 ,   629 ,   959 ,   1483    ,   3837    ,   2093    ,0 };
            const std::uint32_t dim1660JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   9   ,   39  ,   115 ,   153 ,   395 ,   777 ,   1601    ,   3443    ,   3581    ,   1419    ,0 };
            const std::uint32_t dim1661JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   23  ,   61  ,   87  ,   179 ,   463 ,   55  ,   1727    ,   99  ,   7527    ,   15281   ,0 };
            const std::uint32_t dim1662JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   9   ,   49  ,   27  ,   103 ,   221 ,   277 ,   1093    ,   3547    ,   8009    ,   8711    ,0 };
            const std::uint32_t dim1663JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   15  ,   59  ,   79  ,   59  ,   451 ,   763 ,   1687    ,   389 ,   1665    ,   12149   ,0 };
            const std::uint32_t dim1664JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   25  ,   25  ,   37  ,   53  ,   173 ,   1003    ,   1175    ,   3881    ,   4355    ,   6247    ,0 };
            const std::uint32_t dim1665JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   15  ,   31  ,   123 ,   133 ,   79  ,   581 ,   405 ,   2869    ,   2759    ,   2295    ,0 };
            const std::uint32_t dim1666JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   19  ,   3   ,   35  ,   135 ,   287 ,   433 ,   205 ,   2119    ,   6293    ,   2931    ,0 };
            const std::uint32_t dim1667JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   21  ,   29  ,   69  ,   109 ,   401 ,   753 ,   1371    ,   3777    ,   5473    ,   8357    ,0 };
            const std::uint32_t dim1668JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   11  ,   27  ,   101 ,   153 ,   483 ,   639 ,   687 ,   2325    ,   329 ,   12427   ,0 };
            const std::uint32_t dim1669JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   31  ,   41  ,   93  ,   83  ,   121 ,   645 ,   479 ,   1417    ,   1967    ,   2807    ,0 };
            const std::uint32_t dim1670JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   3   ,   29  ,   41  ,   115 ,   41  ,   81  ,   5   ,   1063    ,   943 ,   10151   ,0 };
            const std::uint32_t dim1671JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   5   ,   33  ,   79  ,   245 ,   271 ,   373 ,   1339    ,   1471    ,   4695    ,   12791   ,0 };
            const std::uint32_t dim1672JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   5   ,   5   ,   19  ,   101 ,   109 ,   429 ,   1587    ,   3453    ,   4549    ,   8173    ,0 };
            const std::uint32_t dim1673JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   5   ,   33  ,   5   ,   15  ,   183 ,   241 ,   871 ,   1263    ,   85  ,   13525   ,0 };
            const std::uint32_t dim1674JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   15  ,   5   ,   115 ,   165 ,   451 ,   789 ,   515 ,   3359    ,   1231    ,   3129    ,0 };
            const std::uint32_t dim1675JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   5   ,   45  ,   109 ,   233 ,   369 ,   819 ,   987 ,   3157    ,   5961    ,   5705    ,0 };
            const std::uint32_t dim1676JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   7   ,   63  ,   43  ,   249 ,   95  ,   853 ,   917 ,   1749    ,   4275    ,   10109   ,0 };
            const std::uint32_t dim1677JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   21  ,   5   ,   53  ,   249 ,   3   ,   11  ,   1171    ,   3289    ,   6659    ,   6555    ,0 };
            const std::uint32_t dim1678JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   9   ,   19  ,   35  ,   253 ,   13  ,   229 ,   149 ,   3153    ,   3833    ,   11635   ,0 };
            const std::uint32_t dim1679JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   1   ,   19  ,   127 ,   119 ,   405 ,   19  ,   589 ,   2613    ,   399 ,   3869    ,0 };
            const std::uint32_t dim1680JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   3   ,   11  ,   35  ,   147 ,   11  ,   765 ,   237 ,   2451    ,   5041    ,   4919    ,0 };
            const std::uint32_t dim1681JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   15  ,   7   ,   91  ,   7   ,   5   ,   223 ,   1505    ,   3513    ,   185 ,   2767    ,0 };
            const std::uint32_t dim1682JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   27  ,   17  ,   81  ,   181 ,   11  ,   803 ,   319 ,   3891    ,   4505    ,   6035    ,0 };
            const std::uint32_t dim1683JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   29  ,   13  ,   47  ,   137 ,   301 ,   975 ,   77  ,   3351    ,   6307    ,   2613    ,0 };
            const std::uint32_t dim1684JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   15  ,   41  ,   99  ,   171 ,   465 ,   145 ,   1859    ,   2949    ,   7915    ,   7755    ,0 };
            const std::uint32_t dim1685JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   3   ,   25  ,   123 ,   251 ,   423 ,   921 ,   987 ,   793 ,   2199    ,   1255    ,0 };
            const std::uint32_t dim1686JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   1   ,   63  ,   75  ,   101 ,   219 ,   1013    ,   1761    ,   2171    ,   2763    ,   11185   ,0 };
            const std::uint32_t dim1687JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   13  ,   15  ,   33  ,   147 ,   5   ,   915 ,   1903    ,   2607    ,   3847    ,   167 ,0 };
            const std::uint32_t dim1688JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   23  ,   27  ,   71  ,   17  ,   381 ,   269 ,   603 ,   2303    ,   1399    ,   13795   ,0 };
            const std::uint32_t dim1689JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   29  ,   5   ,   51  ,   151 ,   271 ,   369 ,   595 ,   531 ,   7155    ,   15871   ,0 };
            const std::uint32_t dim1690JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   9   ,   49  ,   49  ,   119 ,   191 ,   105 ,   1203    ,   3431    ,   7063    ,   10831   ,0 };
            const std::uint32_t dim1691JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   31  ,   49  ,   37  ,   147 ,   155 ,   865 ,   339 ,   257 ,   4065    ,   7249    ,0 };
            const std::uint32_t dim1692JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   3   ,   23  ,   127 ,   19  ,   363 ,   733 ,   1059    ,   3693    ,   4623    ,   2853    ,0 };
            const std::uint32_t dim1693JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   3   ,   55  ,   13  ,   177 ,   453 ,   447 ,   183 ,   3247    ,   5923    ,   15485   ,0 };
            const std::uint32_t dim1694JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   3   ,   57  ,   93  ,   13  ,   347 ,   225 ,   535 ,   3187    ,   6047    ,   11315   ,0 };
            const std::uint32_t dim1695JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   17  ,   5   ,   121 ,   35  ,   35  ,   393 ,   1941    ,   1901    ,   7099    ,   2639    ,0 };
            const std::uint32_t dim1696JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   13  ,   43  ,   61  ,   143 ,   291 ,   667 ,   103 ,   3679    ,   7899    ,   3603    ,0 };
            const std::uint32_t dim1697JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   31  ,   57  ,   41  ,   101 ,   455 ,   541 ,   1001    ,   1879    ,   1879    ,   7411    ,0 };
            const std::uint32_t dim1698JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   13  ,   29  ,   113 ,   151 ,   305 ,   593 ,   147 ,   737 ,   6643    ,   14463   ,0 };
            const std::uint32_t dim1699JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   17  ,   55  ,   3   ,   179 ,   277 ,   873 ,   1915    ,   2541    ,   4245    ,   4357    ,0 };
            const std::uint32_t dim1700JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   21  ,   43  ,   97  ,   251 ,   15  ,   443 ,   957 ,   923 ,   7497    ,   9377    ,0 };
            const std::uint32_t dim1701JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   23  ,   19  ,   27  ,   3   ,   35  ,   407 ,   451 ,   3653    ,   813 ,   8833    ,0 };
            const std::uint32_t dim1702JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   15  ,   25  ,   5   ,   165 ,   231 ,   221 ,   1325    ,   641 ,   4545    ,   7667    ,0 };
            const std::uint32_t dim1703JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   13  ,   17  ,   25  ,   225 ,   237 ,   289 ,   187 ,   2881    ,   4723    ,   15579   ,0 };
            const std::uint32_t dim1704JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   15  ,   43  ,   53  ,   241 ,   163 ,   853 ,   491 ,   2497    ,   761 ,   1707    ,0 };
            const std::uint32_t dim1705JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   13  ,   19  ,   83  ,   97  ,   7   ,   639 ,   1985    ,   3553    ,   3971    ,   10661   ,0 };
            const std::uint32_t dim1706JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   15  ,   37  ,   21  ,   139 ,   33  ,   643 ,   63  ,   2213    ,   1807    ,   14483   ,0 };
            const std::uint32_t dim1707JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   3   ,   55  ,   67  ,   45  ,   313 ,   539 ,   1057    ,   455 ,   6473    ,   1499    ,0 };
            const std::uint32_t dim1708JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   1   ,   29  ,   91  ,   133 ,   461 ,   301 ,   539 ,   2001    ,   8189    ,   2009    ,0 };
            const std::uint32_t dim1709JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   17  ,   5   ,   77  ,   221 ,   423 ,   505 ,   419 ,   1987    ,   8171    ,   12985   ,0 };
            const std::uint32_t dim1710JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   21  ,   11  ,   69  ,   53  ,   43  ,   819 ,   1513    ,   1767    ,   2981    ,   4333    ,0 };
            const std::uint32_t dim1711JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   9   ,   29  ,   83  ,   183 ,   9   ,   815 ,   1051    ,   819 ,   2089    ,   13917   ,0 };
            const std::uint32_t dim1712JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   21  ,   41  ,   87  ,   133 ,   149 ,   847 ,   205 ,   1511    ,   2441    ,   13537   ,0 };
            const std::uint32_t dim1713JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   23  ,   1   ,   121 ,   89  ,   349 ,   355 ,   1919    ,   2045    ,   1723    ,   11859   ,0 };
            const std::uint32_t dim1714JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   21  ,   47  ,   111 ,   65  ,   367 ,   505 ,   805 ,   2823    ,   5807    ,   6221    ,0 };
            const std::uint32_t dim1715JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   7   ,   39  ,   35  ,   35  ,   497 ,   411 ,   387 ,   203 ,   1513    ,   15385   ,0 };
            const std::uint32_t dim1716JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   3   ,   7   ,   23  ,   195 ,   353 ,   241 ,   327 ,   1041    ,   4667    ,   4333    ,0 };
            const std::uint32_t dim1717JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   31  ,   51  ,   45  ,   243 ,   485 ,   785 ,   419 ,   1107    ,   7691    ,   2303    ,0 };
            const std::uint32_t dim1718JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   31  ,   1   ,   121 ,   79  ,   263 ,   153 ,   695 ,   3617    ,   7435    ,   11587   ,0 };
            const std::uint32_t dim1719JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   27  ,   33  ,   43  ,   223 ,   153 ,   755 ,   1151    ,   3343    ,   2795    ,   7781    ,0 };
            const std::uint32_t dim1720JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   5   ,   41  ,   39  ,   181 ,   485 ,   129 ,   529 ,   2335    ,   6843    ,   7733    ,0 };
            const std::uint32_t dim1721JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   31  ,   55  ,   117 ,   157 ,   227 ,   125 ,   557 ,   315 ,   3031    ,   8671    ,0 };
            const std::uint32_t dim1722JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   7   ,   15  ,   5   ,   117 ,   149 ,   239 ,   85  ,   341 ,   995 ,   1709    ,   9303    ,0 };
            const std::uint32_t dim1723JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   3   ,   23  ,   17  ,   87  ,   327 ,   929 ,   519 ,   3441    ,   7599    ,   15021   ,0 };
            const std::uint32_t dim1724JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   23  ,   31  ,   81  ,   37  ,   493 ,   451 ,   603 ,   1943    ,   1055    ,   3959    ,0 };
            const std::uint32_t dim1725JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   7   ,   61  ,   61  ,   127 ,   303 ,   675 ,   955 ,   249 ,   7653    ,   8441    ,0 };
            const std::uint32_t dim1726JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   23  ,   1   ,   95  ,   109 ,   155 ,   853 ,   1567    ,   4007    ,   4205    ,   7839    ,0 };
            const std::uint32_t dim1727JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   11  ,   27  ,   57  ,   167 ,   285 ,   421 ,   143 ,   3937    ,   4865    ,   10581   ,0 };
            const std::uint32_t dim1728JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   15  ,   19  ,   49  ,   39  ,   383 ,   549 ,   1563    ,   2499    ,   7889    ,   239 ,0 };
            const std::uint32_t dim1729JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   13  ,   47  ,   61  ,   77  ,   443 ,   961 ,   1979    ,   931 ,   433 ,   6457    ,0 };
            const std::uint32_t dim1730JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   5   ,   1   ,   49  ,   137 ,   417 ,   579 ,   1079    ,   1511    ,   1611    ,   16083   ,0 };
            const std::uint32_t dim1731JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   7   ,   51  ,   43  ,   29  ,   199 ,   525 ,   801 ,   3887    ,   619 ,   3389    ,0 };
            const std::uint32_t dim1732JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   25  ,   23  ,   65  ,   65  ,   201 ,   875 ,   787 ,   3747    ,   7275    ,   6191    ,0 };
            const std::uint32_t dim1733JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   19  ,   21  ,   117 ,   169 ,   39  ,   901 ,   3   ,   3579    ,   6119    ,   2057    ,0 };
            const std::uint32_t dim1734JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   13  ,   59  ,   33  ,   43  ,   237 ,   767 ,   819 ,   3555    ,   1337    ,   13469   ,0 };
            const std::uint32_t dim1735JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   25  ,   51  ,   59  ,   11  ,   427 ,   353 ,   1601    ,   3905    ,   6975    ,   1065    ,0 };
            const std::uint32_t dim1736JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   19  ,   35  ,   43  ,   137 ,   227 ,   17  ,   803 ,   919 ,   6651    ,   3339    ,0 };
            const std::uint32_t dim1737JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   21  ,   21  ,   41  ,   197 ,   373 ,   849 ,   1753    ,   515 ,   4093    ,   15407   ,0 };
            const std::uint32_t dim1738JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   11  ,   5   ,   49  ,   223 ,   351 ,   349 ,   987 ,   1785    ,   269 ,   3037    ,0 };
            const std::uint32_t dim1739JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   3   ,   47  ,   103 ,   225 ,   21  ,   285 ,   1529    ,   399 ,   4951    ,   10767   ,0 };
            const std::uint32_t dim1740JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   25  ,   27  ,   97  ,   87  ,   487 ,   613 ,   607 ,   1905    ,   6019    ,   423 ,0 };
            const std::uint32_t dim1741JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   23  ,   53  ,   23  ,   147 ,   69  ,   781 ,   373 ,   1261    ,   8011    ,   9611    ,0 };
            const std::uint32_t dim1742JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   21  ,   43  ,   67  ,   87  ,   173 ,   57  ,   1147    ,   1841    ,   6031    ,   11261   ,0 };
            const std::uint32_t dim1743JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   29  ,   23  ,   15  ,   113 ,   485 ,   699 ,   259 ,   1175    ,   7489    ,   5119    ,0 };
            const std::uint32_t dim1744JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   15  ,   13  ,   85  ,   219 ,   107 ,   811 ,   1599    ,   2267    ,   8047    ,   12427   ,0 };
            const std::uint32_t dim1745JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   9   ,   7   ,   127 ,   201 ,   275 ,   293 ,   1313    ,   3251    ,   3745    ,   15237   ,0 };
            const std::uint32_t dim1746JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   1   ,   3   ,   57  ,   235 ,   509 ,   353 ,   513 ,   467 ,   1409    ,   4733    ,0 };
            const std::uint32_t dim1747JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   13  ,   43  ,   9   ,   41  ,   39  ,   919 ,   1545    ,   43  ,   8029    ,   1413    ,0 };
            const std::uint32_t dim1748JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   21  ,   7   ,   33  ,   41  ,   161 ,   53  ,   1635    ,   787 ,   6197    ,   4841    ,0 };
            const std::uint32_t dim1749JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   9   ,   29  ,   41  ,   19  ,   161 ,   205 ,   1003    ,   1899    ,   7   ,   4329    ,   11151   ,0 };
            const std::uint32_t dim1750JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   23  ,   23  ,   27  ,   145 ,   375 ,   433 ,   1729    ,   3787    ,   4985    ,   2167    ,0 };
            const std::uint32_t dim1751JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   15  ,   21  ,   77  ,   13  ,   33  ,   227 ,   837 ,   1373    ,   2745    ,   2339    ,0 };
            const std::uint32_t dim1752JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   17  ,   57  ,   31  ,   83  ,   135 ,   535 ,   693 ,   803 ,   1459    ,   319 ,0 };
            const std::uint32_t dim1753JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   11  ,   39  ,   105 ,   111 ,   247 ,   901 ,   395 ,   573 ,   3359    ,   8955    ,0 };
            const std::uint32_t dim1754JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   23  ,   27  ,   99  ,   83  ,   277 ,   229 ,   429 ,   1451    ,   4755    ,   13951   ,0 };
            const std::uint32_t dim1755JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   27  ,   17  ,   37  ,   81  ,   83  ,   991 ,   1509    ,   1931    ,   7389    ,   6053    ,0 };
            const std::uint32_t dim1756JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   27  ,   55  ,   117 ,   93  ,   55  ,   65  ,   155 ,   3933    ,   3159    ,   9507    ,0 };
            const std::uint32_t dim1757JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   15  ,   47  ,   109 ,   79  ,   379 ,   175 ,   419 ,   3285    ,   3207    ,   1675    ,0 };
            const std::uint32_t dim1758JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   31  ,   19  ,   123 ,   229 ,   151 ,   549 ,   1329    ,   3835    ,   511 ,   14679   ,0 };
            const std::uint32_t dim1759JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   25  ,   43  ,   89  ,   145 ,   419 ,   5   ,   1131    ,   2143    ,   7473    ,   14101   ,0 };
            const std::uint32_t dim1760JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   21  ,   43  ,   7   ,   123 ,   15  ,   743 ,   241 ,   1737    ,   2239    ,   11007   ,0 };
            const std::uint32_t dim1761JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   27  ,   3   ,   119 ,   157 ,   361 ,   471 ,   1673    ,   1873    ,   4555    ,   16337   ,0 };
            const std::uint32_t dim1762JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   15  ,   39  ,   95  ,   189 ,   353 ,   605 ,   349 ,   2763    ,   5125    ,   7943    ,0 };
            const std::uint32_t dim1763JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   13  ,   1   ,   45  ,   69  ,   191 ,   183 ,   1967    ,   2455    ,   3879    ,   2397    ,0 };
            const std::uint32_t dim1764JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   3   ,   23  ,   109 ,   123 ,   127 ,   813 ,   1499    ,   39  ,   1991    ,   9767    ,0 };
            const std::uint32_t dim1765JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   7   ,   3   ,   125 ,   93  ,   279 ,   803 ,   1203    ,   3623    ,   4359    ,   4251    ,0 };
            const std::uint32_t dim1766JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   25  ,   57  ,   61  ,   103 ,   219 ,   983 ,   957 ,   895 ,   4077    ,   11799   ,0 };
            const std::uint32_t dim1767JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   21  ,   11  ,   15  ,   137 ,   491 ,   643 ,   1737    ,   3459    ,   4367    ,   5727    ,0 };
            const std::uint32_t dim1768JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   25  ,   57  ,   111 ,   129 ,   101 ,   807 ,   1481    ,   3703    ,   2713    ,   6375    ,0 };
            const std::uint32_t dim1769JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   1   ,   31  ,   59  ,   75  ,   173 ,   209 ,   273 ,   121 ,   747 ,   257 ,   9713    ,0 };
            const std::uint32_t dim1770JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   5   ,   31  ,   107 ,   243 ,   189 ,   407 ,   773 ,   503 ,   6197    ,   9455    ,0 };
            const std::uint32_t dim1771JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   29  ,   25  ,   31  ,   169 ,   393 ,   857 ,   1739    ,   883 ,   2147    ,   15569   ,0 };
            const std::uint32_t dim1772JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   31  ,   47  ,   17  ,   119 ,   499 ,   595 ,   207 ,   1709    ,   4585    ,   12855   ,0 };
            const std::uint32_t dim1773JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   21  ,   33  ,   55  ,   197 ,   349 ,   41  ,   453 ,   1913    ,   2301    ,   6461    ,0 };
            const std::uint32_t dim1774JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   27  ,   37  ,   105 ,   217 ,   145 ,   1007    ,   259 ,   2681    ,   477 ,   15931   ,0 };
            const std::uint32_t dim1775JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   3   ,   39  ,   9   ,   231 ,   395 ,   735 ,   501 ,   1631    ,   2931    ,   11947   ,0 };
            const std::uint32_t dim1776JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   13  ,   61  ,   113 ,   113 ,   473 ,   591 ,   499 ,   2169    ,   6419    ,   10619   ,0 };
            const std::uint32_t dim1777JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   29  ,   63  ,   43  ,   127 ,   243 ,   647 ,   1633    ,   1361    ,   3755    ,   11315   ,0 };
            const std::uint32_t dim1778JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   13  ,   31  ,   111 ,   63  ,   69  ,   1005    ,   1955    ,   339 ,   2415    ,   4855    ,0 };
            const std::uint32_t dim1779JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   25  ,   11  ,   21  ,   1   ,   343 ,   259 ,   1359    ,   597 ,   7029    ,   16229   ,0 };
            const std::uint32_t dim1780JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   27  ,   13  ,   17  ,   43  ,   509 ,   105 ,   347 ,   443 ,   5939    ,   12173   ,0 };
            const std::uint32_t dim1781JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   15  ,   25  ,   93  ,   199 ,   305 ,   725 ,   597 ,   1497    ,   313 ,   10677   ,0 };
            const std::uint32_t dim1782JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   17  ,   7   ,   103 ,   95  ,   83  ,   433 ,   441 ,   2587    ,   3365    ,   14771   ,0 };
            const std::uint32_t dim1783JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   17  ,   7   ,   55  ,   189 ,   451 ,   729 ,   817 ,   243 ,   4089    ,   6569    ,0 };
            const std::uint32_t dim1784JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   5   ,   7   ,   19  ,   113 ,   191 ,   211 ,   1205    ,   4005    ,   3221    ,   7521    ,0 };
            const std::uint32_t dim1785JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   25  ,   49  ,   77  ,   187 ,   105 ,   87  ,   955 ,   2381    ,   1243    ,   11335   ,0 };
            const std::uint32_t dim1786JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   19  ,   63  ,   113 ,   3   ,   7   ,   105 ,   185 ,   1499    ,   6885    ,   9063    ,0 };
            const std::uint32_t dim1787JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   31  ,   47  ,   37  ,   107 ,   31  ,   691 ,   1049    ,   2273    ,   1595    ,   4431    ,0 };
            const std::uint32_t dim1788JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   23  ,   57  ,   51  ,   17  ,   225 ,   551 ,   965 ,   3497    ,   2549    ,   1153    ,0 };
            const std::uint32_t dim1789JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   25  ,   41  ,   123 ,   143 ,   13  ,   437 ,   1081    ,   1625    ,   147 ,   6239    ,0 };
            const std::uint32_t dim1790JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   31  ,   49  ,   17  ,   119 ,   315 ,   155 ,   37  ,   1125    ,   1223    ,   341 ,0 };
            const std::uint32_t dim1791JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   7   ,   9   ,   49  ,   35  ,   223 ,   449 ,   147 ,   317 ,   29  ,   4651    ,   15995   ,0 };
            const std::uint32_t dim1792JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   9   ,   23  ,   97  ,   209 ,   343 ,   279 ,   1947    ,   3465    ,   7775    ,   5779    ,0 };
            const std::uint32_t dim1793JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   1   ,   7   ,   61  ,   111 ,   135 ,   473 ,   105 ,   1529    ,   2855    ,   3457    ,   7053    ,0 };
            const std::uint32_t dim1794JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   29  ,   3   ,   63  ,   25  ,   115 ,   423 ,   1425    ,   1363    ,   77  ,   11485   ,0 };
            const std::uint32_t dim1795JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   23  ,   59  ,   101 ,   87  ,   319 ,   785 ,   1639    ,   3427    ,   3165    ,   11273   ,0 };
            const std::uint32_t dim1796JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   23  ,   7   ,   47  ,   221 ,   137 ,   775 ,   329 ,   1777    ,   3091    ,   4693    ,0 };
            const std::uint32_t dim1797JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   1   ,   33  ,   31  ,   177 ,   481 ,   865 ,   739 ,   97  ,   5113    ,   16371   ,0 };
            const std::uint32_t dim1798JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   31  ,   57  ,   99  ,   241 ,   465 ,   915 ,   1181    ,   225 ,   6795    ,   5743    ,0 };
            const std::uint32_t dim1799JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   13  ,   25  ,   71  ,   119 ,   31  ,   169 ,   1745    ,   4085    ,   2945    ,   13357   ,0 };
            const std::uint32_t dim1800JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   31  ,   61  ,   123 ,   71  ,   375 ,   1003    ,   1303    ,   2149    ,   5867    ,   10523   ,0 };
            const std::uint32_t dim1801JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   21  ,   13  ,   25  ,   147 ,   147 ,   591 ,   259 ,   1707    ,   1777    ,   5869    ,0 };
            const std::uint32_t dim1802JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   7   ,   13  ,   87  ,   227 ,   305 ,   235 ,   1263    ,   953 ,   4509    ,   11375   ,0 };
            const std::uint32_t dim1803JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   11  ,   23  ,   103 ,   177 ,   9   ,   329 ,   1519    ,   2393    ,   6627    ,   14631   ,0 };
            const std::uint32_t dim1804JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   25  ,   19  ,   75  ,   87  ,   361 ,   741 ,   1745    ,   3281    ,   6771    ,   3111    ,0 };
            const std::uint32_t dim1805JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   23  ,   5   ,   1   ,   247 ,   43  ,   61  ,   1489    ,   3537    ,   5079    ,   11545   ,0 };
            const std::uint32_t dim1806JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   9   ,   43  ,   49  ,   213 ,   191 ,   567 ,   1237    ,   681 ,   6715    ,   6471    ,0 };
            const std::uint32_t dim1807JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   31  ,   53  ,   83  ,   53  ,   117 ,   1001    ,   525 ,   841 ,   2891    ,   4281    ,0 };
            const std::uint32_t dim1808JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   21  ,   49  ,   21  ,   215 ,   209 ,   611 ,   1849    ,   969 ,   3081    ,   9485    ,0 };
            const std::uint32_t dim1809JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   13  ,   25  ,   37  ,   31  ,   357 ,   611 ,   83  ,   1615    ,   8137    ,   14505   ,0 };
            const std::uint32_t dim1810JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   29  ,   31  ,   9   ,   27  ,   427 ,   883 ,   555 ,   2559    ,   7039    ,   11345   ,0 };
            const std::uint32_t dim1811JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   3   ,   17  ,   9   ,   251 ,   493 ,   977 ,   1713    ,   2711    ,   4377    ,   3171    ,0 };
            const std::uint32_t dim1812JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   9   ,   1   ,   27  ,   179 ,   345 ,   425 ,   413 ,   2101    ,   3417    ,   1497    ,0 };
            const std::uint32_t dim1813JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   13  ,   33  ,   121 ,   81  ,   247 ,   1003    ,   1405    ,   2769    ,   1919    ,   10807   ,0 };
            const std::uint32_t dim1814JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   29  ,   51  ,   13  ,   101 ,   237 ,   165 ,   1483    ,   3961    ,   2389    ,   8379    ,0 };
            const std::uint32_t dim1815JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   17  ,   3   ,   51  ,   141 ,   295 ,   165 ,   1089    ,   3889    ,   6415    ,   4969    ,0 };
            const std::uint32_t dim1816JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   25  ,   47  ,   1   ,   17  ,   499 ,   409 ,   1417    ,   2975    ,   3935    ,   13363   ,0 };
            const std::uint32_t dim1817JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   7   ,   55  ,   91  ,   121 ,   509 ,   675 ,   1203    ,   795 ,   1225    ,   15329   ,0 };
            const std::uint32_t dim1818JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   3   ,   29  ,   19  ,   103 ,   11  ,   511 ,   799 ,   773 ,   515 ,   9931    ,0 };
            const std::uint32_t dim1819JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   27  ,   63  ,   19  ,   83  ,   213 ,   977 ,   1923    ,   999 ,   7935    ,   2081    ,0 };
            const std::uint32_t dim1820JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   19  ,   17  ,   127 ,   251 ,   417 ,   711 ,   85  ,   2757    ,   6461    ,   83  ,0 };
            const std::uint32_t dim1821JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   11  ,   7   ,   113 ,   127 ,   287 ,   647 ,   1775    ,   3201    ,   2551    ,   13389   ,0 };
            const std::uint32_t dim1822JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   31  ,   33  ,   81  ,   53  ,   207 ,   361 ,   665 ,   2073    ,   4249    ,   6699    ,0 };
            const std::uint32_t dim1823JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   25  ,   43  ,   83  ,   159 ,   31  ,   693 ,   1315    ,   2043    ,   3463    ,   15771   ,0 };
            const std::uint32_t dim1824JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   9   ,   1   ,   93  ,   207 ,   97  ,   293 ,   67  ,   2411    ,   1241    ,   10819   ,0 };
            const std::uint32_t dim1825JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   17  ,   41  ,   113 ,   153 ,   7   ,   499 ,   131 ,   737 ,   7881    ,   2691    ,0 };
            const std::uint32_t dim1826JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   5   ,   3   ,   125 ,   49  ,   63  ,   375 ,   811 ,   3295    ,   7997    ,   1063    ,0 };
            const std::uint32_t dim1827JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   1   ,   27  ,   37  ,   101 ,   179 ,   975 ,   421 ,   2785    ,   8093    ,   11803   ,0 };
            const std::uint32_t dim1828JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   27  ,   35  ,   89  ,   111 ,   481 ,   821 ,   223 ,   2983    ,   2369    ,   4861    ,0 };
            const std::uint32_t dim1829JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   21  ,   59  ,   25  ,   237 ,   73  ,   451 ,   309 ,   241 ,   4955    ,   9889    ,0 };
            const std::uint32_t dim1830JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   25  ,   37  ,   85  ,   29  ,   103 ,   893 ,   337 ,   2831    ,   6679    ,   15171   ,0 };
            const std::uint32_t dim1831JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   13  ,   1   ,   101 ,   109 ,   223 ,   243 ,   1749    ,   3611    ,   4097    ,   14439   ,0 };
            const std::uint32_t dim1832JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   11  ,   31  ,   49  ,   97  ,   181 ,   269 ,   567 ,   1801    ,   3129    ,   2697    ,   15167   ,0 };
            const std::uint32_t dim1833JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   11  ,   11  ,   105 ,   161 ,   163 ,   363 ,   187 ,   3671    ,   6793    ,   4197    ,0 };
            const std::uint32_t dim1834JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   23  ,   61  ,   127 ,   9   ,   101 ,   493 ,   1875    ,   3943    ,   3501    ,   1685    ,0 };
            const std::uint32_t dim1835JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   29  ,   13  ,   11  ,   185 ,   437 ,   151 ,   927 ,   199 ,   7739    ,   14771   ,0 };
            const std::uint32_t dim1836JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   17  ,   17  ,   35  ,   147 ,   387 ,   401 ,   1385    ,   1993    ,   1551    ,   2421    ,0 };
            const std::uint32_t dim1837JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   25  ,   27  ,   1   ,   43  ,   407 ,   503 ,   1917    ,   23  ,   3459    ,   7653    ,0 };
            const std::uint32_t dim1838JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   29  ,   37  ,   69  ,   193 ,   359 ,   901 ,   1661    ,   4049    ,   2923    ,   15553   ,0 };
            const std::uint32_t dim1839JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   31  ,   53  ,   45  ,   5   ,   143 ,   823 ,   483 ,   669 ,   8037    ,   14021   ,0 };
            const std::uint32_t dim1840JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   23  ,   47  ,   105 ,   185 ,   267 ,   347 ,   85  ,   3121    ,   5811    ,   6229    ,0 };
            const std::uint32_t dim1841JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   27  ,   43  ,   25  ,   143 ,   197 ,   425 ,   1537    ,   1701    ,   6061    ,   12125   ,0 };
            const std::uint32_t dim1842JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   31  ,   57  ,   21  ,   21  ,   301 ,   573 ,   947 ,   2087    ,   3135    ,   1767    ,0 };
            const std::uint32_t dim1843JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   23  ,   35  ,   35  ,   191 ,   195 ,   131 ,   1669    ,   3311    ,   4107    ,   9311    ,0 };
            const std::uint32_t dim1844JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   23  ,   13  ,   111 ,   165 ,   283 ,   949 ,   1575    ,   2359    ,   5891    ,   9911    ,0 };
            const std::uint32_t dim1845JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   17  ,   31  ,   31  ,   179 ,   45  ,   475 ,   975 ,   251 ,   353 ,   6331    ,0 };
            const std::uint32_t dim1846JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   15  ,   9   ,   127 ,   35  ,   463 ,   711 ,   1783    ,   837 ,   7859    ,   14299   ,0 };
            const std::uint32_t dim1847JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   31  ,   57  ,   79  ,   7   ,   319 ,   517 ,   677 ,   3923    ,   1363    ,   11355   ,0 };
            const std::uint32_t dim1848JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   17  ,   17  ,   49  ,   171 ,   95  ,   519 ,   775 ,   2265    ,   7953    ,   617 ,0 };
            const std::uint32_t dim1849JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   3   ,   35  ,   87  ,   185 ,   369 ,   795 ,   1171    ,   3777    ,   4983    ,   1153    ,0 };
            const std::uint32_t dim1850JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   9   ,   3   ,   1   ,   131 ,   275 ,   921 ,   507 ,   1877    ,   1573    ,   6231    ,0 };
            const std::uint32_t dim1851JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   7   ,   53  ,   77  ,   255 ,   329 ,   449 ,   1859    ,   3625    ,   7027    ,   9921    ,0 };
            const std::uint32_t dim1852JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   1   ,   47  ,   57  ,   111 ,   303 ,   749 ,   689 ,   2963    ,   8085    ,   9097    ,0 };
            const std::uint32_t dim1853JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   19  ,   47  ,   61  ,   3   ,   481 ,   371 ,   1737    ,   287 ,   5485    ,   15433   ,0 };
            const std::uint32_t dim1854JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   23  ,   45  ,   33  ,   83  ,   483 ,   411 ,   257 ,   749 ,   3959    ,   10269   ,0 };
            const std::uint32_t dim1855JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   25  ,   15  ,   11  ,   181 ,   131 ,   943 ,   125 ,   3367    ,   2429    ,   2151    ,0 };
            const std::uint32_t dim1856JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   25  ,   35  ,   37  ,   163 ,   399 ,   575 ,   843 ,   1567    ,   4401    ,   14757   ,0 };
            const std::uint32_t dim1857JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   5   ,   3   ,   31  ,   199 ,   479 ,   525 ,   973 ,   2843    ,   7831    ,   6693    ,0 };
            const std::uint32_t dim1858JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   21  ,   7   ,   123 ,   31  ,   207 ,   741 ,   425 ,   2139    ,   2965    ,   1017    ,0 };
            const std::uint32_t dim1859JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   11  ,   3   ,   31  ,   61  ,   85  ,   303 ,   627 ,   1995    ,   3211    ,   5747    ,   14897   ,0 };
            const std::uint32_t dim1860JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   9   ,   25  ,   45  ,   73  ,   427 ,   945 ,   1505    ,   1121    ,   7585    ,   13115   ,0 };
            const std::uint32_t dim1861JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   9   ,   43  ,   75  ,   63  ,   445 ,   709 ,   645 ,   1105    ,   1375    ,   12303   ,0 };
            const std::uint32_t dim1862JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   25  ,   37  ,   101 ,   209 ,   239 ,   429 ,   1455    ,   3587    ,   4231    ,   6501    ,0 };
            const std::uint32_t dim1863JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   21  ,   23  ,   113 ,   227 ,   151 ,   97  ,   367 ,   889 ,   7675    ,   14093   ,0 };
            const std::uint32_t dim1864JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   13  ,   31  ,   63  ,   7   ,   31  ,   973 ,   1935    ,   53  ,   4941    ,   9057    ,0 };
            const std::uint32_t dim1865JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   21  ,   23  ,   79  ,   43  ,   255 ,   1003    ,   1741    ,   1003    ,   355 ,   3839    ,0 };
            const std::uint32_t dim1866JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   31  ,   17  ,   45  ,   235 ,   271 ,   711 ,   61  ,   235 ,   513 ,   11321   ,0 };
            const std::uint32_t dim1867JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   29  ,   35  ,   43  ,   115 ,   9   ,   787 ,   325 ,   625 ,   7905    ,   8191    ,   29233   ,0 };
            const std::uint32_t dim1868JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   5   ,   17  ,   67  ,   161 ,   357 ,   163 ,   1129    ,   3819    ,   3601    ,   5961    ,   9259    ,0 };
            const std::uint32_t dim1869JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   13  ,   25  ,   17  ,   83  ,   41  ,   463 ,   879 ,   1881    ,   1107    ,   4337    ,   409 ,   8633    ,0 };
            const std::uint32_t dim1870JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   17  ,   45  ,   127 ,   213 ,   285 ,   791 ,   479 ,   3153    ,   3001    ,   16207   ,   32669   ,0 };
            const std::uint32_t dim1871JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   23  ,   41  ,   103 ,   209 ,   81  ,   903 ,   1787    ,   907 ,   161 ,   15739   ,   17367   ,0 };
            const std::uint32_t dim1872JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   17  ,   61  ,   69  ,   251 ,   321 ,   361 ,   905 ,   1081    ,   5749    ,   2639    ,   21195   ,0 };
            const std::uint32_t dim1873JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   27  ,   39  ,   61  ,   161 ,   139 ,   837 ,   579 ,   1979    ,   4413    ,   8701    ,   16301   ,0 };
            const std::uint32_t dim1874JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   3   ,   49  ,   111 ,   77  ,   423 ,   491 ,   1489    ,   2615    ,   4997    ,   3695    ,   15109   ,0 };
            const std::uint32_t dim1875JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   7   ,   31  ,   3   ,   53  ,   113 ,   45  ,   767 ,   1561    ,   2925    ,   605 ,   3211    ,   8413    ,0 };
            const std::uint32_t dim1876JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   31  ,   29  ,   65  ,   13  ,   19  ,   159 ,   639 ,   2155    ,   2699    ,   7001    ,   15575   ,0 };
            const std::uint32_t dim1877JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   1   ,   3   ,   33  ,   37  ,   89  ,   189 ,   661 ,   1685    ,   503 ,   6037    ,   12993   ,   9571    ,0 };
            const std::uint32_t dim1878JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   31  ,   13  ,   41  ,   35  ,   217 ,   193 ,   1273    ,   443 ,   1385    ,   13661   ,   14873   ,0 };
            const std::uint32_t dim1879JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   3   ,   9   ,   123 ,   251 ,   155 ,   545 ,   813 ,   317 ,   5127    ,   15305   ,   5571    ,0 };
            const std::uint32_t dim1880JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   3   ,   39  ,   41  ,   39  ,   273 ,   881 ,   809 ,   1643    ,   687 ,   5525    ,   3473    ,0 };
            const std::uint32_t dim1881JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   7   ,   25  ,   25  ,   27  ,   263 ,   773 ,   155 ,   1541    ,   7545    ,   873 ,   32713   ,0 };
            const std::uint32_t dim1882JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   1   ,   49  ,   57  ,   17  ,   433 ,   73  ,   635 ,   1073    ,   7459    ,   15653   ,   47  ,0 };
            const std::uint32_t dim1883JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   1   ,   5   ,   65  ,   105 ,   353 ,   361 ,   339 ,   3983    ,   2707    ,   10165   ,   20883   ,0 };
            const std::uint32_t dim1884JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   23  ,   29  ,   125 ,   223 ,   463 ,   493 ,   1989    ,   1583    ,   8153    ,   13475   ,   5789    ,0 };
            const std::uint32_t dim1885JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   27  ,   39  ,   61  ,   127 ,   387 ,   215 ,   1769    ,   2279    ,   7883    ,   1491    ,   29625   ,0 };
            const std::uint32_t dim1886JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   5   ,   5   ,   13  ,   11  ,   47  ,   409 ,   673 ,   1927    ,   1277    ,   6971    ,   8195    ,   22663   ,0 };
            const std::uint32_t dim1887JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   1   ,   53  ,   123 ,   187 ,   25  ,   29  ,   1107    ,   1929    ,   6995    ,   5081    ,   8861    ,0 };
            const std::uint32_t dim1888JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   25  ,   27  ,   53  ,   65  ,   239 ,   299 ,   21  ,   3389    ,   1587    ,   1437    ,   26209   ,0 };
            const std::uint32_t dim1889JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   15  ,   35  ,   37  ,   105 ,   169 ,   843 ,   623 ,   3763    ,   7101    ,   5245    ,   17203   ,0 };
            const std::uint32_t dim1890JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   21  ,   7   ,   29  ,   29  ,   465 ,   149 ,   189 ,   1115    ,   6471    ,   11275   ,   28769   ,0 };
            const std::uint32_t dim1891JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   31  ,   1   ,   99  ,   101 ,   321 ,   675 ,   1631    ,   1371    ,   7733    ,   1697    ,   4437    ,0 };
            const std::uint32_t dim1892JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   7   ,   27  ,   47  ,   207 ,   295 ,   787 ,   1539    ,   2233    ,   7849    ,   15843   ,   11149   ,0 };
            const std::uint32_t dim1893JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   17  ,   29  ,   61  ,   143 ,   289 ,   939 ,   729 ,   297 ,   1513    ,   4387    ,   3347    ,0 };
            const std::uint32_t dim1894JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   15  ,   25  ,   125 ,   13  ,   157 ,   377 ,   317 ,   827 ,   5137    ,   829 ,   21215   ,0 };
            const std::uint32_t dim1895JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   17  ,   37  ,   79  ,   87  ,   163 ,   847 ,   1009    ,   2259    ,   6543    ,   8697    ,   4837    ,0 };
            const std::uint32_t dim1896JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   29  ,   7   ,   13  ,   91  ,   279 ,   439 ,   691 ,   4047    ,   159 ,   9403    ,   27735   ,0 };
            const std::uint32_t dim1897JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   23  ,   61  ,   53  ,   93  ,   343 ,   349 ,   355 ,   1275    ,   3573    ,   12847   ,   8969    ,0 };
            const std::uint32_t dim1898JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   1   ,   49  ,   47  ,   255 ,   371 ,   511 ,   579 ,   2385    ,   2237    ,   2015    ,   23973   ,0 };
            const std::uint32_t dim1899JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   11  ,   15  ,   31  ,   13  ,   121 ,   399 ,   957 ,   731 ,   3743    ,   1573    ,   2293    ,   27755   ,0 };
            const std::uint32_t dim1900JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   5   ,   23  ,   19  ,   57  ,   211 ,   133 ,   197 ,   379 ,   1037    ,   625 ,   9405    ,   11547   ,0 };
            const std::uint32_t dim1901JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   7   ,   13  ,   75  ,   93  ,   415 ,   551 ,   1885    ,   2259    ,   23  ,   14321   ,   21509   ,0 };
            const std::uint32_t dim1902JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   29  ,   37  ,   23  ,   59  ,   199 ,   559 ,   1761    ,   821 ,   5077    ,   12017   ,   16505   ,0 };
            const std::uint32_t dim1903JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   19  ,   29  ,   31  ,   101 ,   121 ,   605 ,   1679    ,   2317    ,   3359    ,   13557   ,   17567   ,0 };
            const std::uint32_t dim1904JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   3   ,   5   ,   45  ,   201 ,   401 ,   689 ,   1775    ,   3615    ,   2641    ,   14149   ,   29241   ,0 };
            const std::uint32_t dim1905JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   5   ,   9   ,   13  ,   51  ,   101 ,   41  ,   347 ,   57  ,   613 ,   5813    ,   3753    ,   22007   ,0 };
            const std::uint32_t dim1906JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   19  ,   59  ,   57  ,   57  ,   405 ,   647 ,   1943    ,   353 ,   1691    ,   9287    ,   29567   ,0 };
            const std::uint32_t dim1907JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   29  ,   11  ,   51  ,   137 ,   163 ,   365 ,   153 ,   3791    ,   5367    ,   4649    ,   11255   ,0 };
            const std::uint32_t dim1908JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   27  ,   37  ,   99  ,   211 ,   377 ,   543 ,   649 ,   2107    ,   3511    ,   10385   ,   1093    ,0 };
            const std::uint32_t dim1909JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   29  ,   25  ,   85  ,   75  ,   55  ,   75  ,   825 ,   2129    ,   6867    ,   9053    ,   22687   ,0 };
            const std::uint32_t dim1910JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   1   ,   19  ,   57  ,   29  ,   99  ,   369 ,   107 ,   1187    ,   2919    ,   6163    ,   15209   ,   7911    ,0 };
            const std::uint32_t dim1911JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   25  ,   55  ,   111 ,   197 ,   329 ,   307 ,   1531    ,   1753    ,   1275    ,   5543    ,   23411   ,0 };
            const std::uint32_t dim1912JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   21  ,   59  ,   97  ,   211 ,   117 ,   331 ,   1919    ,   1763    ,   1755    ,   12517   ,   16579   ,0 };
            const std::uint32_t dim1913JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   5   ,   37  ,   21  ,   229 ,   109 ,   341 ,   421 ,   2413    ,   785 ,   3251    ,   10245   ,0 };
            const std::uint32_t dim1914JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   27  ,   3   ,   89  ,   15  ,   455 ,   53  ,   1447    ,   137 ,   681 ,   7811    ,   16817   ,0 };
            const std::uint32_t dim1915JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   9   ,   57  ,   45  ,   101 ,   459 ,   801 ,   409 ,   911 ,   749 ,   11875   ,   6039    ,0 };
            const std::uint32_t dim1916JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   23  ,   31  ,   49  ,   105 ,   255 ,   485 ,   1587    ,   1137    ,   2113    ,   16313   ,   19073   ,0 };
            const std::uint32_t dim1917JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   31  ,   59  ,   117 ,   213 ,   293 ,   195 ,   991 ,   3531    ,   157 ,   1747    ,   20883   ,0 };
            const std::uint32_t dim1918JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   17  ,   31  ,   63  ,   33  ,   415 ,   341 ,   779 ,   423 ,   5661    ,   2533    ,   23031   ,0 };
            const std::uint32_t dim1919JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   3   ,   11  ,   41  ,   69  ,   117 ,   441 ,   3   ,   885 ,   3387    ,   4291    ,   497 ,   9991    ,0 };
            const std::uint32_t dim1920JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   15  ,   27  ,   29  ,   17  ,   109 ,   315 ,   433 ,   291 ,   577 ,   3209    ,   3305    ,   6759    ,0 };
            const std::uint32_t dim1921JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   1   ,   29  ,   37  ,   75  ,   139 ,   243 ,   217 ,   319 ,   1025    ,   2415    ,   5957    ,   8303    ,0 };
            const std::uint32_t dim1922JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   15  ,   41  ,   19  ,   21  ,   279 ,   563 ,   893 ,   1391    ,   4907    ,   14381   ,   7165    ,0 };
            const std::uint32_t dim1923JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   21  ,   35  ,   23  ,   139 ,   441 ,   463 ,   563 ,   155 ,   2009    ,   14887   ,   30943   ,0 };
            const std::uint32_t dim1924JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   3   ,   23  ,   23  ,   13  ,   157 ,   511 ,   401 ,   1573    ,   3019    ,   1791    ,   587 ,   10927   ,0 };
            const std::uint32_t dim1925JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   5   ,   1   ,   45  ,   127 ,   85  ,   27  ,   729 ,   993 ,   1487    ,   5577    ,   14113   ,   23163   ,0 };
            const std::uint32_t dim1926JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   31  ,   15  ,   19  ,   7   ,   503 ,   359 ,   595 ,   1471    ,   2587    ,   7827    ,   31497   ,0 };
            const std::uint32_t dim1927JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   13  ,   29  ,   35  ,   49  ,   381 ,   677 ,   407 ,   2681    ,   7923    ,   2917    ,   4001    ,0 };
            const std::uint32_t dim1928JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   25  ,   51  ,   3   ,   33  ,   229 ,   105 ,   1449    ,   417 ,   2577    ,   5185    ,   18737   ,0 };
            const std::uint32_t dim1929JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   29  ,   17  ,   9   ,   185 ,   253 ,   929 ,   1267    ,   2559    ,   2271    ,   10501   ,   21687   ,0 };
            const std::uint32_t dim1930JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   9   ,   29  ,   89  ,   193 ,   309 ,   385 ,   73  ,   1835    ,   5193    ,   10235   ,   29827   ,0 };
            const std::uint32_t dim1931JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   29  ,   23  ,   9   ,   119 ,   325 ,   277 ,   1883    ,   613 ,   6299    ,   10799   ,   16271   ,0 };
            const std::uint32_t dim1932JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   29  ,   55  ,   71  ,   5   ,   99  ,   303 ,   1853    ,   2225    ,   3047    ,   16019   ,   23257   ,0 };
            const std::uint32_t dim1933JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   19  ,   19  ,   35  ,   39  ,   389 ,   737 ,   433 ,   1489    ,   5903    ,   10181   ,   11249   ,0 };
            const std::uint32_t dim1934JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   15  ,   13  ,   21  ,   191 ,   369 ,   939 ,   1353    ,   2645    ,   221 ,   49  ,   14783   ,0 };
            const std::uint32_t dim1935JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   17  ,   5   ,   21  ,   121 ,   359 ,   863 ,   893 ,   2887    ,   4431    ,   5245    ,   20865   ,0 };
            const std::uint32_t dim1936JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   15  ,   25  ,   59  ,   37  ,   263 ,   425 ,   1143    ,   3843    ,   4955    ,   6639    ,   8411    ,0 };
            const std::uint32_t dim1937JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   15  ,   3   ,   5   ,   123 ,   131 ,   229 ,   93  ,   113 ,   3609    ,   2007    ,   7709    ,   32141   ,0 };
            const std::uint32_t dim1938JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   11  ,   25  ,   43  ,   103 ,   199 ,   243 ,   533 ,   1947    ,   683 ,   1013    ,   13155   ,   29877   ,0 };
            const std::uint32_t dim1939JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   9   ,   17  ,   41  ,   57  ,   99  ,   137 ,   839 ,   1437    ,   3997    ,   2473    ,   10169   ,   20253   ,0 };
            const std::uint32_t dim1940JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   19  ,   49  ,   55  ,   185 ,   175 ,   319 ,   1173    ,   1049    ,   5289    ,   3297    ,   23755   ,0 };
            const std::uint32_t dim1941JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   25  ,   7   ,   81  ,   119 ,   319 ,   743 ,   1655    ,   3719    ,   5731    ,   11015   ,   11309   ,0 };
            const std::uint32_t dim1942JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   31  ,   53  ,   61  ,   119 ,   207 ,   689 ,   81  ,   367 ,   2495    ,   1965    ,   15559   ,0 };
            const std::uint32_t dim1943JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   21  ,   47  ,   9   ,   199 ,   273 ,   397 ,   1293    ,   2709    ,   3687    ,   5755    ,   6015    ,0 };
            const std::uint32_t dim1944JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   1   ,   7   ,   55  ,   55  ,   343 ,   363 ,   1207    ,   3731    ,   7489    ,   2365    ,   25301   ,0 };
            const std::uint32_t dim1945JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   7   ,   3   ,   31  ,   87  ,   15  ,   327 ,   479 ,   177 ,   1261    ,   913 ,   4189    ,   4565    ,0 };
            const std::uint32_t dim1946JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   19  ,   37  ,   29  ,   17  ,   185 ,   827 ,   239 ,   281 ,   287 ,   16105   ,   23549   ,0 };
            const std::uint32_t dim1947JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   3   ,   23  ,   17  ,   73  ,   123 ,   287 ,   665 ,   297 ,   215 ,   359 ,   11741   ,   29159   ,0 };
            const std::uint32_t dim1948JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   11  ,   13  ,   45  ,   35  ,   81  ,   211 ,   257 ,   655 ,   911 ,   5949    ,   9597    ,   11677   ,0 };
            const std::uint32_t dim1949JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   15  ,   7   ,   39  ,   31  ,   103 ,   341 ,   871 ,   299 ,   635 ,   951 ,   13669   ,   30083   ,0 };
            const std::uint32_t dim1950JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   7   ,   15  ,   55  ,   45  ,   375 ,   711 ,   1339    ,   3045    ,   4691    ,   13247   ,   14611   ,0 };
            const std::uint32_t dim1951JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   9   ,   19  ,   33  ,   67  ,   91  ,   83  ,   541 ,   1229    ,   3209    ,   2783    ,   11519   ,   10729   ,0 };
            const std::uint32_t dim1952JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   15  ,   15  ,   89  ,   7   ,   173 ,   809 ,   1229    ,   117 ,   2323    ,   15145   ,   2863    ,0 };
            const std::uint32_t dim1953JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   1   ,   55  ,   39  ,   187 ,   491 ,   675 ,   1357    ,   1109    ,   2701    ,   14891   ,   17061   ,0 };
            const std::uint32_t dim1954JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   5   ,   7   ,   47  ,   127 ,   111 ,   481 ,   177 ,   1553    ,   2949    ,   6403    ,   1993    ,   26227   ,0 };
            const std::uint32_t dim1955JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   11  ,   31  ,   3   ,   111 ,   193 ,   445 ,   359 ,   1039    ,   667 ,   7463    ,   7983    ,   10901   ,0 };
            const std::uint32_t dim1956JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   29  ,   17  ,   15  ,   69  ,   111 ,   27  ,   647 ,   3377    ,   185 ,   12083   ,   21197   ,0 };
            const std::uint32_t dim1957JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   5   ,   17  ,   57  ,   5   ,   189 ,   383 ,   407 ,   145 ,   1185    ,   3307    ,   12373   ,   28531   ,0 };
            const std::uint32_t dim1958JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   9   ,   23  ,   43  ,   41  ,   19  ,   127 ,   687 ,   1841    ,   3707    ,   4983    ,   14585   ,   15253   ,0 };
            const std::uint32_t dim1959JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   9   ,   13  ,   61  ,   13  ,   113 ,   43  ,   423 ,   1073    ,   1843    ,   1071    ,   7869    ,   21137   ,0 };
            const std::uint32_t dim1960JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   3   ,   7   ,   43  ,   87  ,   185 ,   375 ,   699 ,   283 ,   3265    ,   4905    ,   9317    ,   3055    ,0 };
            const std::uint32_t dim1961JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   9   ,   17  ,   15  ,   47  ,   73  ,   211 ,   37  ,   427 ,   3841    ,   2801    ,   12131   ,   19619   ,0 };
            const std::uint32_t dim1962JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   7   ,   17  ,   35  ,   53  ,   67  ,   221 ,   97  ,   199 ,   2825    ,   1997    ,   9903    ,   3003    ,0 };
            const std::uint32_t dim1963JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   23  ,   53  ,   69  ,   225 ,   413 ,   307 ,   553 ,   2631    ,   6499    ,   6277    ,   30337   ,0 };
            const std::uint32_t dim1964JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   5   ,   23  ,   85  ,   193 ,   437 ,   607 ,   397 ,   2003    ,   4345    ,   3575    ,   27939   ,0 };
            const std::uint32_t dim1965JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   13  ,   13  ,   45  ,   117 ,   191 ,   143 ,   477 ,   473 ,   3051    ,   5903    ,   6253    ,   22679   ,0 };
            const std::uint32_t dim1966JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   13  ,   31  ,   49  ,   31  ,   217 ,   119 ,   893 ,   1415    ,   1633    ,   7573    ,   8353    ,   32231   ,0 };
            const std::uint32_t dim1967JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   5   ,   29  ,   47  ,   25  ,   3   ,   425 ,   883 ,   1461    ,   3679    ,   6635    ,   9103    ,   26793   ,0 };
            const std::uint32_t dim1968JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   15  ,   11  ,   27  ,   87  ,   31  ,   153 ,   115 ,   1573    ,   745 ,   6515    ,   14321   ,   21301   ,0 };
            const std::uint32_t dim1969JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   11  ,   15  ,   57  ,   41  ,   157 ,   147 ,   867 ,   1959    ,   943 ,   6431    ,   14581   ,   9579    ,0 };
            const std::uint32_t dim1970JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   9   ,   5   ,   13  ,   1   ,   203 ,   317 ,   185 ,   1569    ,   3621    ,   4873    ,   13249   ,   19153   ,0 };
            const std::uint32_t dim1971JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   5   ,   5   ,   29  ,   41  ,   3   ,   37  ,   919 ,   1037    ,   237 ,   4699    ,   12011   ,   18669   ,0 };
            const std::uint32_t dim1972JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   1   ,   21  ,   1   ,   55  ,   195 ,   289 ,   635 ,   981 ,   1395    ,   1827    ,   7481    ,   19163   ,0 };
            const std::uint32_t dim1973JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   15  ,   15  ,   89  ,   109 ,   17  ,   111 ,   815 ,   2637    ,   6917    ,   7973    ,   9471    ,0 };
            const std::uint32_t dim1974JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   9   ,   25  ,   73  ,   101 ,   417 ,   519 ,   1697    ,   2861    ,   2281    ,   10959   ,   30433   ,0 };
            const std::uint32_t dim1975JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   3   ,   21  ,   51  ,   89  ,   157 ,   181 ,   307 ,   355 ,   661 ,   4885    ,   12411   ,   23473   ,0 };
            const std::uint32_t dim1976JoeKuoD5Init[]   =   {   1   ,   1   ,   1   ,   15  ,   17  ,   37  ,   19  ,   139 ,   205 ,   73  ,   97  ,   2463    ,   2785    ,   9355    ,   23989   ,0 };
            const std::uint32_t dim1977JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   7   ,   39  ,   117 ,   191 ,   395 ,   539 ,   1823    ,   2333    ,   1205    ,   14131   ,   2301    ,0 };
            const std::uint32_t dim1978JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   21  ,   11  ,   49  ,   43  ,   381 ,   15  ,   1743    ,   641 ,   95  ,   10581   ,   15437   ,0 };
            const std::uint32_t dim1979JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   5   ,   53  ,   55  ,   23  ,   265 ,   163 ,   173 ,   1399    ,   7257    ,   15097   ,   13491   ,0 };
            const std::uint32_t dim1980JoeKuoD5Init[]   =   {   1   ,   3   ,   3   ,   13  ,   27  ,   55  ,   97  ,   51  ,   469 ,   7   ,   871 ,   3213    ,   5719    ,   871 ,   11669   ,0 };
            const std::uint32_t dim1981JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   29  ,   35  ,   47  ,   31  ,   77  ,   335 ,   537 ,   1695    ,   461 ,   14417   ,   23945   ,0 };
            const std::uint32_t dim1982JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   13  ,   1   ,   47  ,   97  ,   113 ,   235 ,   593 ,   1437    ,   3893    ,   5299    ,   857 ,   451 ,0 };
            const std::uint32_t dim1983JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   3   ,   3   ,   53  ,   51  ,   203 ,   177 ,   205 ,   773 ,   281 ,   7689    ,   8039    ,   7275    ,0 };
            const std::uint32_t dim1984JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   3   ,   3   ,   37  ,   33  ,   113 ,   429 ,   791 ,   1593    ,   3259    ,   1275    ,   11113   ,   16001   ,0 };
            const std::uint32_t dim1985JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   7   ,   27  ,   9   ,   109 ,   229 ,   453 ,   633 ,   2047    ,   1803    ,   4127    ,   3453    ,   15625   ,0 };
            const std::uint32_t dim1986JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   15  ,   17  ,   59  ,   15  ,   73  ,   105 ,   627 ,   1181    ,   2925    ,   2077    ,   16067   ,   15829   ,0 };
            const std::uint32_t dim1987JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   1   ,   15  ,   41  ,   1   ,   143 ,   493 ,   261 ,   845 ,   737 ,   6249    ,   7663    ,   32439   ,0 };
            const std::uint32_t dim1988JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   11  ,   45  ,   101 ,   227 ,   227 ,   211 ,   243 ,   2817    ,   179 ,   3361    ,   20535   ,0 };
            const std::uint32_t dim1989JoeKuoD5Init[]   =   {   1   ,   3   ,   1   ,   3   ,   11  ,   25  ,   105 ,   173 ,   249 ,   465 ,   853 ,   2365    ,   5035    ,   11541   ,   5481    ,0 };
            const std::uint32_t dim1990JoeKuoD5Init[]   =   {   1   ,   3   ,   5   ,   9   ,   21  ,   29  ,   77  ,   245 ,   311 ,   879 ,   1007    ,   2545    ,   1561    ,   2949    ,   24855   ,0 };
            const std::uint32_t dim1991JoeKuoD5Init[]   =   {   1   ,   1   ,   5   ,   13  ,   1   ,   31  ,   105 ,   151 ,   127 ,   413 ,   553 ,   645 ,   863 ,   15943   ,   32731   ,0 };
            const std::uint32_t dim1992JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   11  ,   21  ,   13  ,   71  ,   229 ,   283 ,   493 ,   1445    ,   15  ,   4681    ,   3137    ,   18199   ,0 };
            const std::uint32_t dim1993JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   27  ,   17  ,   37  ,   213 ,   253 ,   117 ,   205 ,   1489    ,   2997    ,   6483    ,   17201   ,0 };
            const std::uint32_t dim1994JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   13  ,   3   ,   29  ,   83  ,   109 ,   503 ,   139 ,   1119    ,   59  ,   5259    ,   8289    ,   7717    ,0 };
            const std::uint32_t dim1995JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   13  ,   13  ,   5   ,   65  ,   231 ,   117 ,   1009    ,   163 ,   21  ,   7639    ,   16275   ,   10661   ,0 };
            const std::uint32_t dim1996JoeKuoD5Init[]   =   {   1   ,   3   ,   7   ,   7   ,   19  ,   63  ,   31  ,   211 ,   487 ,   277 ,   27  ,   3685    ,   5371    ,   8157    ,   29735   ,0 };
            const std::uint32_t dim1997JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   1   ,   11  ,   49  ,   113 ,   191 ,   3   ,   923 ,   797 ,   2055    ,   3999    ,   8511    ,   23931   ,0 };
            const std::uint32_t dim1998JoeKuoD5Init[]   =   {   1   ,   1   ,   7   ,   7   ,   13  ,   27  ,   87  ,   43  ,   433 ,   401 ,   1441    ,   1301    ,   2639    ,   5773    ,   12431   ,0 };
            const std::uint32_t dim1999JoeKuoD5Init[]   =   {   1   ,   1   ,   3   ,   15  ,   21  ,   55  ,   17  ,   57  ,   449 ,   811 ,   519 ,   2329    ,   7607    ,   4255    ,   2845    ,0 };

            const std::uint32_t * const JoeKuoD5initializers[1999]
            =
            {
                dim1JoeKuoD5Init,
                dim2JoeKuoD5Init,
                dim3JoeKuoD5Init,
                dim4JoeKuoD5Init,
                dim5JoeKuoD5Init,
                dim6JoeKuoD5Init,
                dim7JoeKuoD5Init,
                dim8JoeKuoD5Init,
                dim9JoeKuoD5Init,
                dim10JoeKuoD5Init,
                dim11JoeKuoD5Init,
                dim12JoeKuoD5Init,
                dim13JoeKuoD5Init,
                dim14JoeKuoD5Init,
                dim15JoeKuoD5Init,
                dim16JoeKuoD5Init,
                dim17JoeKuoD5Init,
                dim18JoeKuoD5Init,
                dim19JoeKuoD5Init,
                dim20JoeKuoD5Init,
                dim21JoeKuoD5Init,
                dim22JoeKuoD5Init,
                dim23JoeKuoD5Init,
                dim24JoeKuoD5Init,
                dim25JoeKuoD5Init,
                dim26JoeKuoD5Init,
                dim27JoeKuoD5Init,
                dim28JoeKuoD5Init,
                dim29JoeKuoD5Init,
                dim30JoeKuoD5Init,
                dim31JoeKuoD5Init,
                dim32JoeKuoD5Init,
                dim33JoeKuoD5Init,
                dim34JoeKuoD5Init,
                dim35JoeKuoD5Init,
                dim36JoeKuoD5Init,
                dim37JoeKuoD5Init,
                dim38JoeKuoD5Init,
                dim39JoeKuoD5Init,
                dim40JoeKuoD5Init,
                dim41JoeKuoD5Init,
                dim42JoeKuoD5Init,
                dim43JoeKuoD5Init,
                dim44JoeKuoD5Init,
                dim45JoeKuoD5Init,
                dim46JoeKuoD5Init,
                dim47JoeKuoD5Init,
                dim48JoeKuoD5Init,
                dim49JoeKuoD5Init,
                dim50JoeKuoD5Init,
                dim51JoeKuoD5Init,
                dim52JoeKuoD5Init,
                dim53JoeKuoD5Init,
                dim54JoeKuoD5Init,
                dim55JoeKuoD5Init,
                dim56JoeKuoD5Init,
                dim57JoeKuoD5Init,
                dim58JoeKuoD5Init,
                dim59JoeKuoD5Init,
                dim60JoeKuoD5Init,
                dim61JoeKuoD5Init,
                dim62JoeKuoD5Init,
                dim63JoeKuoD5Init,
                dim64JoeKuoD5Init,
                dim65JoeKuoD5Init,
                dim66JoeKuoD5Init,
                dim67JoeKuoD5Init,
                dim68JoeKuoD5Init,
                dim69JoeKuoD5Init,
                dim70JoeKuoD5Init,
                dim71JoeKuoD5Init,
                dim72JoeKuoD5Init,
                dim73JoeKuoD5Init,
                dim74JoeKuoD5Init,
                dim75JoeKuoD5Init,
                dim76JoeKuoD5Init,
                dim77JoeKuoD5Init,
                dim78JoeKuoD5Init,
                dim79JoeKuoD5Init,
                dim80JoeKuoD5Init,
                dim81JoeKuoD5Init,
                dim82JoeKuoD5Init,
                dim83JoeKuoD5Init,
                dim84JoeKuoD5Init,
                dim85JoeKuoD5Init,
                dim86JoeKuoD5Init,
                dim87JoeKuoD5Init,
                dim88JoeKuoD5Init,
                dim89JoeKuoD5Init,
                dim90JoeKuoD5Init,
                dim91JoeKuoD5Init,
                dim92JoeKuoD5Init,
                dim93JoeKuoD5Init,
                dim94JoeKuoD5Init,
                dim95JoeKuoD5Init,
                dim96JoeKuoD5Init,
                dim97JoeKuoD5Init,
                dim98JoeKuoD5Init,
                dim99JoeKuoD5Init,
                dim100JoeKuoD5Init,
                dim101JoeKuoD5Init,
                dim102JoeKuoD5Init,
                dim103JoeKuoD5Init,
                dim104JoeKuoD5Init,
                dim105JoeKuoD5Init,
                dim106JoeKuoD5Init,
                dim107JoeKuoD5Init,
                dim108JoeKuoD5Init,
                dim109JoeKuoD5Init,
                dim110JoeKuoD5Init,
                dim111JoeKuoD5Init,
                dim112JoeKuoD5Init,
                dim113JoeKuoD5Init,
                dim114JoeKuoD5Init,
                dim115JoeKuoD5Init,
                dim116JoeKuoD5Init,
                dim117JoeKuoD5Init,
                dim118JoeKuoD5Init,
                dim119JoeKuoD5Init,
                dim120JoeKuoD5Init,
                dim121JoeKuoD5Init,
                dim122JoeKuoD5Init,
                dim123JoeKuoD5Init,
                dim124JoeKuoD5Init,
                dim125JoeKuoD5Init,
                dim126JoeKuoD5Init,
                dim127JoeKuoD5Init,
                dim128JoeKuoD5Init,
                dim129JoeKuoD5Init,
                dim130JoeKuoD5Init,
                dim131JoeKuoD5Init,
                dim132JoeKuoD5Init,
                dim133JoeKuoD5Init,
                dim134JoeKuoD5Init,
                dim135JoeKuoD5Init,
                dim136JoeKuoD5Init,
                dim137JoeKuoD5Init,
                dim138JoeKuoD5Init,
                dim139JoeKuoD5Init,
                dim140JoeKuoD5Init,
                dim141JoeKuoD5Init,
                dim142JoeKuoD5Init,
                dim143JoeKuoD5Init,
                dim144JoeKuoD5Init,
                dim145JoeKuoD5Init,
                dim146JoeKuoD5Init,
                dim147JoeKuoD5Init,
                dim148JoeKuoD5Init,
                dim149JoeKuoD5Init,
                dim150JoeKuoD5Init,
                dim151JoeKuoD5Init,
                dim152JoeKuoD5Init,
                dim153JoeKuoD5Init,
                dim154JoeKuoD5Init,
                dim155JoeKuoD5Init,
                dim156JoeKuoD5Init,
                dim157JoeKuoD5Init,
                dim158JoeKuoD5Init,
                dim159JoeKuoD5Init,
                dim160JoeKuoD5Init,
                dim161JoeKuoD5Init,
                dim162JoeKuoD5Init,
                dim163JoeKuoD5Init,
                dim164JoeKuoD5Init,
                dim165JoeKuoD5Init,
                dim166JoeKuoD5Init,
                dim167JoeKuoD5Init,
                dim168JoeKuoD5Init,
                dim169JoeKuoD5Init,
                dim170JoeKuoD5Init,
                dim171JoeKuoD5Init,
                dim172JoeKuoD5Init,
                dim173JoeKuoD5Init,
                dim174JoeKuoD5Init,
                dim175JoeKuoD5Init,
                dim176JoeKuoD5Init,
                dim177JoeKuoD5Init,
                dim178JoeKuoD5Init,
                dim179JoeKuoD5Init,
                dim180JoeKuoD5Init,
                dim181JoeKuoD5Init,
                dim182JoeKuoD5Init,
                dim183JoeKuoD5Init,
                dim184JoeKuoD5Init,
                dim185JoeKuoD5Init,
                dim186JoeKuoD5Init,
                dim187JoeKuoD5Init,
                dim188JoeKuoD5Init,
                dim189JoeKuoD5Init,
                dim190JoeKuoD5Init,
                dim191JoeKuoD5Init,
                dim192JoeKuoD5Init,
                dim193JoeKuoD5Init,
                dim194JoeKuoD5Init,
                dim195JoeKuoD5Init,
                dim196JoeKuoD5Init,
                dim197JoeKuoD5Init,
                dim198JoeKuoD5Init,
                dim199JoeKuoD5Init,
                dim200JoeKuoD5Init,
                dim201JoeKuoD5Init,
                dim202JoeKuoD5Init,
                dim203JoeKuoD5Init,
                dim204JoeKuoD5Init,
                dim205JoeKuoD5Init,
                dim206JoeKuoD5Init,
                dim207JoeKuoD5Init,
                dim208JoeKuoD5Init,
                dim209JoeKuoD5Init,
                dim210JoeKuoD5Init,
                dim211JoeKuoD5Init,
                dim212JoeKuoD5Init,
                dim213JoeKuoD5Init,
                dim214JoeKuoD5Init,
                dim215JoeKuoD5Init,
                dim216JoeKuoD5Init,
                dim217JoeKuoD5Init,
                dim218JoeKuoD5Init,
                dim219JoeKuoD5Init,
                dim220JoeKuoD5Init,
                dim221JoeKuoD5Init,
                dim222JoeKuoD5Init,
                dim223JoeKuoD5Init,
                dim224JoeKuoD5Init,
                dim225JoeKuoD5Init,
                dim226JoeKuoD5Init,
                dim227JoeKuoD5Init,
                dim228JoeKuoD5Init,
                dim229JoeKuoD5Init,
                dim230JoeKuoD5Init,
                dim231JoeKuoD5Init,
                dim232JoeKuoD5Init,
                dim233JoeKuoD5Init,
                dim234JoeKuoD5Init,
                dim235JoeKuoD5Init,
                dim236JoeKuoD5Init,
                dim237JoeKuoD5Init,
                dim238JoeKuoD5Init,
                dim239JoeKuoD5Init,
                dim240JoeKuoD5Init,
                dim241JoeKuoD5Init,
                dim242JoeKuoD5Init,
                dim243JoeKuoD5Init,
                dim244JoeKuoD5Init,
                dim245JoeKuoD5Init,
                dim246JoeKuoD5Init,
                dim247JoeKuoD5Init,
                dim248JoeKuoD5Init,
                dim249JoeKuoD5Init,
                dim250JoeKuoD5Init,
                dim251JoeKuoD5Init,
                dim252JoeKuoD5Init,
                dim253JoeKuoD5Init,
                dim254JoeKuoD5Init,
                dim255JoeKuoD5Init,
                dim256JoeKuoD5Init,
                dim257JoeKuoD5Init,
                dim258JoeKuoD5Init,
                dim259JoeKuoD5Init,
                dim260JoeKuoD5Init,
                dim261JoeKuoD5Init,
                dim262JoeKuoD5Init,
                dim263JoeKuoD5Init,
                dim264JoeKuoD5Init,
                dim265JoeKuoD5Init,
                dim266JoeKuoD5Init,
                dim267JoeKuoD5Init,
                dim268JoeKuoD5Init,
                dim269JoeKuoD5Init,
                dim270JoeKuoD5Init,
                dim271JoeKuoD5Init,
                dim272JoeKuoD5Init,
                dim273JoeKuoD5Init,
                dim274JoeKuoD5Init,
                dim275JoeKuoD5Init,
                dim276JoeKuoD5Init,
                dim277JoeKuoD5Init,
                dim278JoeKuoD5Init,
                dim279JoeKuoD5Init,
                dim280JoeKuoD5Init,
                dim281JoeKuoD5Init,
                dim282JoeKuoD5Init,
                dim283JoeKuoD5Init,
                dim284JoeKuoD5Init,
                dim285JoeKuoD5Init,
                dim286JoeKuoD5Init,
                dim287JoeKuoD5Init,
                dim288JoeKuoD5Init,
                dim289JoeKuoD5Init,
                dim290JoeKuoD5Init,
                dim291JoeKuoD5Init,
                dim292JoeKuoD5Init,
                dim293JoeKuoD5Init,
                dim294JoeKuoD5Init,
                dim295JoeKuoD5Init,
                dim296JoeKuoD5Init,
                dim297JoeKuoD5Init,
                dim298JoeKuoD5Init,
                dim299JoeKuoD5Init,
                dim300JoeKuoD5Init,
                dim301JoeKuoD5Init,
                dim302JoeKuoD5Init,
                dim303JoeKuoD5Init,
                dim304JoeKuoD5Init,
                dim305JoeKuoD5Init,
                dim306JoeKuoD5Init,
                dim307JoeKuoD5Init,
                dim308JoeKuoD5Init,
                dim309JoeKuoD5Init,
                dim310JoeKuoD5Init,
                dim311JoeKuoD5Init,
                dim312JoeKuoD5Init,
                dim313JoeKuoD5Init,
                dim314JoeKuoD5Init,
                dim315JoeKuoD5Init,
                dim316JoeKuoD5Init,
                dim317JoeKuoD5Init,
                dim318JoeKuoD5Init,
                dim319JoeKuoD5Init,
                dim320JoeKuoD5Init,
                dim321JoeKuoD5Init,
                dim322JoeKuoD5Init,
                dim323JoeKuoD5Init,
                dim324JoeKuoD5Init,
                dim325JoeKuoD5Init,
                dim326JoeKuoD5Init,
                dim327JoeKuoD5Init,
                dim328JoeKuoD5Init,
                dim329JoeKuoD5Init,
                dim330JoeKuoD5Init,
                dim331JoeKuoD5Init,
                dim332JoeKuoD5Init,
                dim333JoeKuoD5Init,
                dim334JoeKuoD5Init,
                dim335JoeKuoD5Init,
                dim336JoeKuoD5Init,
                dim337JoeKuoD5Init,
                dim338JoeKuoD5Init,
                dim339JoeKuoD5Init,
                dim340JoeKuoD5Init,
                dim341JoeKuoD5Init,
                dim342JoeKuoD5Init,
                dim343JoeKuoD5Init,
                dim344JoeKuoD5Init,
                dim345JoeKuoD5Init,
                dim346JoeKuoD5Init,
                dim347JoeKuoD5Init,
                dim348JoeKuoD5Init,
                dim349JoeKuoD5Init,
                dim350JoeKuoD5Init,
                dim351JoeKuoD5Init,
                dim352JoeKuoD5Init,
                dim353JoeKuoD5Init,
                dim354JoeKuoD5Init,
                dim355JoeKuoD5Init,
                dim356JoeKuoD5Init,
                dim357JoeKuoD5Init,
                dim358JoeKuoD5Init,
                dim359JoeKuoD5Init,
                dim360JoeKuoD5Init,
                dim361JoeKuoD5Init,
                dim362JoeKuoD5Init,
                dim363JoeKuoD5Init,
                dim364JoeKuoD5Init,
                dim365JoeKuoD5Init,
                dim366JoeKuoD5Init,
                dim367JoeKuoD5Init,
                dim368JoeKuoD5Init,
                dim369JoeKuoD5Init,
                dim370JoeKuoD5Init,
                dim371JoeKuoD5Init,
                dim372JoeKuoD5Init,
                dim373JoeKuoD5Init,
                dim374JoeKuoD5Init,
                dim375JoeKuoD5Init,
                dim376JoeKuoD5Init,
                dim377JoeKuoD5Init,
                dim378JoeKuoD5Init,
                dim379JoeKuoD5Init,
                dim380JoeKuoD5Init,
                dim381JoeKuoD5Init,
                dim382JoeKuoD5Init,
                dim383JoeKuoD5Init,
                dim384JoeKuoD5Init,
                dim385JoeKuoD5Init,
                dim386JoeKuoD5Init,
                dim387JoeKuoD5Init,
                dim388JoeKuoD5Init,
                dim389JoeKuoD5Init,
                dim390JoeKuoD5Init,
                dim391JoeKuoD5Init,
                dim392JoeKuoD5Init,
                dim393JoeKuoD5Init,
                dim394JoeKuoD5Init,
                dim395JoeKuoD5Init,
                dim396JoeKuoD5Init,
                dim397JoeKuoD5Init,
                dim398JoeKuoD5Init,
                dim399JoeKuoD5Init,
                dim400JoeKuoD5Init,
                dim401JoeKuoD5Init,
                dim402JoeKuoD5Init,
                dim403JoeKuoD5Init,
                dim404JoeKuoD5Init,
                dim405JoeKuoD5Init,
                dim406JoeKuoD5Init,
                dim407JoeKuoD5Init,
                dim408JoeKuoD5Init,
                dim409JoeKuoD5Init,
                dim410JoeKuoD5Init,
                dim411JoeKuoD5Init,
                dim412JoeKuoD5Init,
                dim413JoeKuoD5Init,
                dim414JoeKuoD5Init,
                dim415JoeKuoD5Init,
                dim416JoeKuoD5Init,
                dim417JoeKuoD5Init,
                dim418JoeKuoD5Init,
                dim419JoeKuoD5Init,
                dim420JoeKuoD5Init,
                dim421JoeKuoD5Init,
                dim422JoeKuoD5Init,
                dim423JoeKuoD5Init,
                dim424JoeKuoD5Init,
                dim425JoeKuoD5Init,
                dim426JoeKuoD5Init,
                dim427JoeKuoD5Init,
                dim428JoeKuoD5Init,
                dim429JoeKuoD5Init,
                dim430JoeKuoD5Init,
                dim431JoeKuoD5Init,
                dim432JoeKuoD5Init,
                dim433JoeKuoD5Init,
                dim434JoeKuoD5Init,
                dim435JoeKuoD5Init,
                dim436JoeKuoD5Init,
                dim437JoeKuoD5Init,
                dim438JoeKuoD5Init,
                dim439JoeKuoD5Init,
                dim440JoeKuoD5Init,
                dim441JoeKuoD5Init,
                dim442JoeKuoD5Init,
                dim443JoeKuoD5Init,
                dim444JoeKuoD5Init,
                dim445JoeKuoD5Init,
                dim446JoeKuoD5Init,
                dim447JoeKuoD5Init,
                dim448JoeKuoD5Init,
                dim449JoeKuoD5Init,
                dim450JoeKuoD5Init,
                dim451JoeKuoD5Init,
                dim452JoeKuoD5Init,
                dim453JoeKuoD5Init,
                dim454JoeKuoD5Init,
                dim455JoeKuoD5Init,
                dim456JoeKuoD5Init,
                dim457JoeKuoD5Init,
                dim458JoeKuoD5Init,
                dim459JoeKuoD5Init,
                dim460JoeKuoD5Init,
                dim461JoeKuoD5Init,
                dim462JoeKuoD5Init,
                dim463JoeKuoD5Init,
                dim464JoeKuoD5Init,
                dim465JoeKuoD5Init,
                dim466JoeKuoD5Init,
                dim467JoeKuoD5Init,
                dim468JoeKuoD5Init,
                dim469JoeKuoD5Init,
                dim470JoeKuoD5Init,
                dim471JoeKuoD5Init,
                dim472JoeKuoD5Init,
                dim473JoeKuoD5Init,
                dim474JoeKuoD5Init,
                dim475JoeKuoD5Init,
                dim476JoeKuoD5Init,
                dim477JoeKuoD5Init,
                dim478JoeKuoD5Init,
                dim479JoeKuoD5Init,
                dim480JoeKuoD5Init,
                dim481JoeKuoD5Init,
                dim482JoeKuoD5Init,
                dim483JoeKuoD5Init,
                dim484JoeKuoD5Init,
                dim485JoeKuoD5Init,
                dim486JoeKuoD5Init,
                dim487JoeKuoD5Init,
                dim488JoeKuoD5Init,
                dim489JoeKuoD5Init,
                dim490JoeKuoD5Init,
                dim491JoeKuoD5Init,
                dim492JoeKuoD5Init,
                dim493JoeKuoD5Init,
                dim494JoeKuoD5Init,
                dim495JoeKuoD5Init,
                dim496JoeKuoD5Init,
                dim497JoeKuoD5Init,
                dim498JoeKuoD5Init,
                dim499JoeKuoD5Init,
                dim500JoeKuoD5Init,
                dim501JoeKuoD5Init,
                dim502JoeKuoD5Init,
                dim503JoeKuoD5Init,
                dim504JoeKuoD5Init,
                dim505JoeKuoD5Init,
                dim506JoeKuoD5Init,
                dim507JoeKuoD5Init,
                dim508JoeKuoD5Init,
                dim509JoeKuoD5Init,
                dim510JoeKuoD5Init,
                dim511JoeKuoD5Init,
                dim512JoeKuoD5Init,
                dim513JoeKuoD5Init,
                dim514JoeKuoD5Init,
                dim515JoeKuoD5Init,
                dim516JoeKuoD5Init,
                dim517JoeKuoD5Init,
                dim518JoeKuoD5Init,
                dim519JoeKuoD5Init,
                dim520JoeKuoD5Init,
                dim521JoeKuoD5Init,
                dim522JoeKuoD5Init,
                dim523JoeKuoD5Init,
                dim524JoeKuoD5Init,
                dim525JoeKuoD5Init,
                dim526JoeKuoD5Init,
                dim527JoeKuoD5Init,
                dim528JoeKuoD5Init,
                dim529JoeKuoD5Init,
                dim530JoeKuoD5Init,
                dim531JoeKuoD5Init,
                dim532JoeKuoD5Init,
                dim533JoeKuoD5Init,
                dim534JoeKuoD5Init,
                dim535JoeKuoD5Init,
                dim536JoeKuoD5Init,
                dim537JoeKuoD5Init,
                dim538JoeKuoD5Init,
                dim539JoeKuoD5Init,
                dim540JoeKuoD5Init,
                dim541JoeKuoD5Init,
                dim542JoeKuoD5Init,
                dim543JoeKuoD5Init,
                dim544JoeKuoD5Init,
                dim545JoeKuoD5Init,
                dim546JoeKuoD5Init,
                dim547JoeKuoD5Init,
                dim548JoeKuoD5Init,
                dim549JoeKuoD5Init,
                dim550JoeKuoD5Init,
                dim551JoeKuoD5Init,
                dim552JoeKuoD5Init,
                dim553JoeKuoD5Init,
                dim554JoeKuoD5Init,
                dim555JoeKuoD5Init,
                dim556JoeKuoD5Init,
                dim557JoeKuoD5Init,
                dim558JoeKuoD5Init,
                dim559JoeKuoD5Init,
                dim560JoeKuoD5Init,
                dim561JoeKuoD5Init,
                dim562JoeKuoD5Init,
                dim563JoeKuoD5Init,
                dim564JoeKuoD5Init,
                dim565JoeKuoD5Init,
                dim566JoeKuoD5Init,
                dim567JoeKuoD5Init,
                dim568JoeKuoD5Init,
                dim569JoeKuoD5Init,
                dim570JoeKuoD5Init,
                dim571JoeKuoD5Init,
                dim572JoeKuoD5Init,
                dim573JoeKuoD5Init,
                dim574JoeKuoD5Init,
                dim575JoeKuoD5Init,
                dim576JoeKuoD5Init,
                dim577JoeKuoD5Init,
                dim578JoeKuoD5Init,
                dim579JoeKuoD5Init,
                dim580JoeKuoD5Init,
                dim581JoeKuoD5Init,
                dim582JoeKuoD5Init,
                dim583JoeKuoD5Init,
                dim584JoeKuoD5Init,
                dim585JoeKuoD5Init,
                dim586JoeKuoD5Init,
                dim587JoeKuoD5Init,
                dim588JoeKuoD5Init,
                dim589JoeKuoD5Init,
                dim590JoeKuoD5Init,
                dim591JoeKuoD5Init,
                dim592JoeKuoD5Init,
                dim593JoeKuoD5Init,
                dim594JoeKuoD5Init,
                dim595JoeKuoD5Init,
                dim596JoeKuoD5Init,
                dim597JoeKuoD5Init,
                dim598JoeKuoD5Init,
                dim599JoeKuoD5Init,
                dim600JoeKuoD5Init,
                dim601JoeKuoD5Init,
                dim602JoeKuoD5Init,
                dim603JoeKuoD5Init,
                dim604JoeKuoD5Init,
                dim605JoeKuoD5Init,
                dim606JoeKuoD5Init,
                dim607JoeKuoD5Init,
                dim608JoeKuoD5Init,
                dim609JoeKuoD5Init,
                dim610JoeKuoD5Init,
                dim611JoeKuoD5Init,
                dim612JoeKuoD5Init,
                dim613JoeKuoD5Init,
                dim614JoeKuoD5Init,
                dim615JoeKuoD5Init,
                dim616JoeKuoD5Init,
                dim617JoeKuoD5Init,
                dim618JoeKuoD5Init,
                dim619JoeKuoD5Init,
                dim620JoeKuoD5Init,
                dim621JoeKuoD5Init,
                dim622JoeKuoD5Init,
                dim623JoeKuoD5Init,
                dim624JoeKuoD5Init,
                dim625JoeKuoD5Init,
                dim626JoeKuoD5Init,
                dim627JoeKuoD5Init,
                dim628JoeKuoD5Init,
                dim629JoeKuoD5Init,
                dim630JoeKuoD5Init,
                dim631JoeKuoD5Init,
                dim632JoeKuoD5Init,
                dim633JoeKuoD5Init,
                dim634JoeKuoD5Init,
                dim635JoeKuoD5Init,
                dim636JoeKuoD5Init,
                dim637JoeKuoD5Init,
                dim638JoeKuoD5Init,
                dim639JoeKuoD5Init,
                dim640JoeKuoD5Init,
                dim641JoeKuoD5Init,
                dim642JoeKuoD5Init,
                dim643JoeKuoD5Init,
                dim644JoeKuoD5Init,
                dim645JoeKuoD5Init,
                dim646JoeKuoD5Init,
                dim647JoeKuoD5Init,
                dim648JoeKuoD5Init,
                dim649JoeKuoD5Init,
                dim650JoeKuoD5Init,
                dim651JoeKuoD5Init,
                dim652JoeKuoD5Init,
                dim653JoeKuoD5Init,
                dim654JoeKuoD5Init,
                dim655JoeKuoD5Init,
                dim656JoeKuoD5Init,
                dim657JoeKuoD5Init,
                dim658JoeKuoD5Init,
                dim659JoeKuoD5Init,
                dim660JoeKuoD5Init,
                dim661JoeKuoD5Init,
                dim662JoeKuoD5Init,
                dim663JoeKuoD5Init,
                dim664JoeKuoD5Init,
                dim665JoeKuoD5Init,
                dim666JoeKuoD5Init,
                dim667JoeKuoD5Init,
                dim668JoeKuoD5Init,
                dim669JoeKuoD5Init,
                dim670JoeKuoD5Init,
                dim671JoeKuoD5Init,
                dim672JoeKuoD5Init,
                dim673JoeKuoD5Init,
                dim674JoeKuoD5Init,
                dim675JoeKuoD5Init,
                dim676JoeKuoD5Init,
                dim677JoeKuoD5Init,
                dim678JoeKuoD5Init,
                dim679JoeKuoD5Init,
                dim680JoeKuoD5Init,
                dim681JoeKuoD5Init,
                dim682JoeKuoD5Init,
                dim683JoeKuoD5Init,
                dim684JoeKuoD5Init,
                dim685JoeKuoD5Init,
                dim686JoeKuoD5Init,
                dim687JoeKuoD5Init,
                dim688JoeKuoD5Init,
                dim689JoeKuoD5Init,
                dim690JoeKuoD5Init,
                dim691JoeKuoD5Init,
                dim692JoeKuoD5Init,
                dim693JoeKuoD5Init,
                dim694JoeKuoD5Init,
                dim695JoeKuoD5Init,
                dim696JoeKuoD5Init,
                dim697JoeKuoD5Init,
                dim698JoeKuoD5Init,
                dim699JoeKuoD5Init,
                dim700JoeKuoD5Init,
                dim701JoeKuoD5Init,
                dim702JoeKuoD5Init,
                dim703JoeKuoD5Init,
                dim704JoeKuoD5Init,
                dim705JoeKuoD5Init,
                dim706JoeKuoD5Init,
                dim707JoeKuoD5Init,
                dim708JoeKuoD5Init,
                dim709JoeKuoD5Init,
                dim710JoeKuoD5Init,
                dim711JoeKuoD5Init,
                dim712JoeKuoD5Init,
                dim713JoeKuoD5Init,
                dim714JoeKuoD5Init,
                dim715JoeKuoD5Init,
                dim716JoeKuoD5Init,
                dim717JoeKuoD5Init,
                dim718JoeKuoD5Init,
                dim719JoeKuoD5Init,
                dim720JoeKuoD5Init,
                dim721JoeKuoD5Init,
                dim722JoeKuoD5Init,
                dim723JoeKuoD5Init,
                dim724JoeKuoD5Init,
                dim725JoeKuoD5Init,
                dim726JoeKuoD5Init,
                dim727JoeKuoD5Init,
                dim728JoeKuoD5Init,
                dim729JoeKuoD5Init,
                dim730JoeKuoD5Init,
                dim731JoeKuoD5Init,
                dim732JoeKuoD5Init,
                dim733JoeKuoD5Init,
                dim734JoeKuoD5Init,
                dim735JoeKuoD5Init,
                dim736JoeKuoD5Init,
                dim737JoeKuoD5Init,
                dim738JoeKuoD5Init,
                dim739JoeKuoD5Init,
                dim740JoeKuoD5Init,
                dim741JoeKuoD5Init,
                dim742JoeKuoD5Init,
                dim743JoeKuoD5Init,
                dim744JoeKuoD5Init,
                dim745JoeKuoD5Init,
                dim746JoeKuoD5Init,
                dim747JoeKuoD5Init,
                dim748JoeKuoD5Init,
                dim749JoeKuoD5Init,
                dim750JoeKuoD5Init,
                dim751JoeKuoD5Init,
                dim752JoeKuoD5Init,
                dim753JoeKuoD5Init,
                dim754JoeKuoD5Init,
                dim755JoeKuoD5Init,
                dim756JoeKuoD5Init,
                dim757JoeKuoD5Init,
                dim758JoeKuoD5Init,
                dim759JoeKuoD5Init,
                dim760JoeKuoD5Init,
                dim761JoeKuoD5Init,
                dim762JoeKuoD5Init,
                dim763JoeKuoD5Init,
                dim764JoeKuoD5Init,
                dim765JoeKuoD5Init,
                dim766JoeKuoD5Init,
                dim767JoeKuoD5Init,
                dim768JoeKuoD5Init,
                dim769JoeKuoD5Init,
                dim770JoeKuoD5Init,
                dim771JoeKuoD5Init,
                dim772JoeKuoD5Init,
                dim773JoeKuoD5Init,
                dim774JoeKuoD5Init,
                dim775JoeKuoD5Init,
                dim776JoeKuoD5Init,
                dim777JoeKuoD5Init,
                dim778JoeKuoD5Init,
                dim779JoeKuoD5Init,
                dim780JoeKuoD5Init,
                dim781JoeKuoD5Init,
                dim782JoeKuoD5Init,
                dim783JoeKuoD5Init,
                dim784JoeKuoD5Init,
                dim785JoeKuoD5Init,
                dim786JoeKuoD5Init,
                dim787JoeKuoD5Init,
                dim788JoeKuoD5Init,
                dim789JoeKuoD5Init,
                dim790JoeKuoD5Init,
                dim791JoeKuoD5Init,
                dim792JoeKuoD5Init,
                dim793JoeKuoD5Init,
                dim794JoeKuoD5Init,
                dim795JoeKuoD5Init,
                dim796JoeKuoD5Init,
                dim797JoeKuoD5Init,
                dim798JoeKuoD5Init,
                dim799JoeKuoD5Init,
                dim800JoeKuoD5Init,
                dim801JoeKuoD5Init,
                dim802JoeKuoD5Init,
                dim803JoeKuoD5Init,
                dim804JoeKuoD5Init,
                dim805JoeKuoD5Init,
                dim806JoeKuoD5Init,
                dim807JoeKuoD5Init,
                dim808JoeKuoD5Init,
                dim809JoeKuoD5Init,
                dim810JoeKuoD5Init,
                dim811JoeKuoD5Init,
                dim812JoeKuoD5Init,
                dim813JoeKuoD5Init,
                dim814JoeKuoD5Init,
                dim815JoeKuoD5Init,
                dim816JoeKuoD5Init,
                dim817JoeKuoD5Init,
                dim818JoeKuoD5Init,
                dim819JoeKuoD5Init,
                dim820JoeKuoD5Init,
                dim821JoeKuoD5Init,
                dim822JoeKuoD5Init,
                dim823JoeKuoD5Init,
                dim824JoeKuoD5Init,
                dim825JoeKuoD5Init,
                dim826JoeKuoD5Init,
                dim827JoeKuoD5Init,
                dim828JoeKuoD5Init,
                dim829JoeKuoD5Init,
                dim830JoeKuoD5Init,
                dim831JoeKuoD5Init,
                dim832JoeKuoD5Init,
                dim833JoeKuoD5Init,
                dim834JoeKuoD5Init,
                dim835JoeKuoD5Init,
                dim836JoeKuoD5Init,
                dim837JoeKuoD5Init,
                dim838JoeKuoD5Init,
                dim839JoeKuoD5Init,
                dim840JoeKuoD5Init,
                dim841JoeKuoD5Init,
                dim842JoeKuoD5Init,
                dim843JoeKuoD5Init,
                dim844JoeKuoD5Init,
                dim845JoeKuoD5Init,
                dim846JoeKuoD5Init,
                dim847JoeKuoD5Init,
                dim848JoeKuoD5Init,
                dim849JoeKuoD5Init,
                dim850JoeKuoD5Init,
                dim851JoeKuoD5Init,
                dim852JoeKuoD5Init,
                dim853JoeKuoD5Init,
                dim854JoeKuoD5Init,
                dim855JoeKuoD5Init,
                dim856JoeKuoD5Init,
                dim857JoeKuoD5Init,
                dim858JoeKuoD5Init,
                dim859JoeKuoD5Init,
                dim860JoeKuoD5Init,
                dim861JoeKuoD5Init,
                dim862JoeKuoD5Init,
                dim863JoeKuoD5Init,
                dim864JoeKuoD5Init,
                dim865JoeKuoD5Init,
                dim866JoeKuoD5Init,
                dim867JoeKuoD5Init,
                dim868JoeKuoD5Init,
                dim869JoeKuoD5Init,
                dim870JoeKuoD5Init,
                dim871JoeKuoD5Init,
                dim872JoeKuoD5Init,
                dim873JoeKuoD5Init,
                dim874JoeKuoD5Init,
                dim875JoeKuoD5Init,
                dim876JoeKuoD5Init,
                dim877JoeKuoD5Init,
                dim878JoeKuoD5Init,
                dim879JoeKuoD5Init,
                dim880JoeKuoD5Init,
                dim881JoeKuoD5Init,
                dim882JoeKuoD5Init,
                dim883JoeKuoD5Init,
                dim884JoeKuoD5Init,
                dim885JoeKuoD5Init,
                dim886JoeKuoD5Init,
                dim887JoeKuoD5Init,
                dim888JoeKuoD5Init,
                dim889JoeKuoD5Init,
                dim890JoeKuoD5Init,
                dim891JoeKuoD5Init,
                dim892JoeKuoD5Init,
                dim893JoeKuoD5Init,
                dim894JoeKuoD5Init,
                dim895JoeKuoD5Init,
                dim896JoeKuoD5Init,
                dim897JoeKuoD5Init,
                dim898JoeKuoD5Init,
                dim899JoeKuoD5Init,
                dim900JoeKuoD5Init,
                dim901JoeKuoD5Init,
                dim902JoeKuoD5Init,
                dim903JoeKuoD5Init,
                dim904JoeKuoD5Init,
                dim905JoeKuoD5Init,
                dim906JoeKuoD5Init,
                dim907JoeKuoD5Init,
                dim908JoeKuoD5Init,
                dim909JoeKuoD5Init,
                dim910JoeKuoD5Init,
                dim911JoeKuoD5Init,
                dim912JoeKuoD5Init,
                dim913JoeKuoD5Init,
                dim914JoeKuoD5Init,
                dim915JoeKuoD5Init,
                dim916JoeKuoD5Init,
                dim917JoeKuoD5Init,
                dim918JoeKuoD5Init,
                dim919JoeKuoD5Init,
                dim920JoeKuoD5Init,
                dim921JoeKuoD5Init,
                dim922JoeKuoD5Init,
                dim923JoeKuoD5Init,
                dim924JoeKuoD5Init,
                dim925JoeKuoD5Init,
                dim926JoeKuoD5Init,
                dim927JoeKuoD5Init,
                dim928JoeKuoD5Init,
                dim929JoeKuoD5Init,
                dim930JoeKuoD5Init,
                dim931JoeKuoD5Init,
                dim932JoeKuoD5Init,
                dim933JoeKuoD5Init,
                dim934JoeKuoD5Init,
                dim935JoeKuoD5Init,
                dim936JoeKuoD5Init,
                dim937JoeKuoD5Init,
                dim938JoeKuoD5Init,
                dim939JoeKuoD5Init,
                dim940JoeKuoD5Init,
                dim941JoeKuoD5Init,
                dim942JoeKuoD5Init,
                dim943JoeKuoD5Init,
                dim944JoeKuoD5Init,
                dim945JoeKuoD5Init,
                dim946JoeKuoD5Init,
                dim947JoeKuoD5Init,
                dim948JoeKuoD5Init,
                dim949JoeKuoD5Init,
                dim950JoeKuoD5Init,
                dim951JoeKuoD5Init,
                dim952JoeKuoD5Init,
                dim953JoeKuoD5Init,
                dim954JoeKuoD5Init,
                dim955JoeKuoD5Init,
                dim956JoeKuoD5Init,
                dim957JoeKuoD5Init,
                dim958JoeKuoD5Init,
                dim959JoeKuoD5Init,
                dim960JoeKuoD5Init,
                dim961JoeKuoD5Init,
                dim962JoeKuoD5Init,
                dim963JoeKuoD5Init,
                dim964JoeKuoD5Init,
                dim965JoeKuoD5Init,
                dim966JoeKuoD5Init,
                dim967JoeKuoD5Init,
                dim968JoeKuoD5Init,
                dim969JoeKuoD5Init,
                dim970JoeKuoD5Init,
                dim971JoeKuoD5Init,
                dim972JoeKuoD5Init,
                dim973JoeKuoD5Init,
                dim974JoeKuoD5Init,
                dim975JoeKuoD5Init,
                dim976JoeKuoD5Init,
                dim977JoeKuoD5Init,
                dim978JoeKuoD5Init,
                dim979JoeKuoD5Init,
                dim980JoeKuoD5Init,
                dim981JoeKuoD5Init,
                dim982JoeKuoD5Init,
                dim983JoeKuoD5Init,
                dim984JoeKuoD5Init,
                dim985JoeKuoD5Init,
                dim986JoeKuoD5Init,
                dim987JoeKuoD5Init,
                dim988JoeKuoD5Init,
                dim989JoeKuoD5Init,
                dim990JoeKuoD5Init,
                dim991JoeKuoD5Init,
                dim992JoeKuoD5Init,
                dim993JoeKuoD5Init,
                dim994JoeKuoD5Init,
                dim995JoeKuoD5Init,
                dim996JoeKuoD5Init,
                dim997JoeKuoD5Init,
                dim998JoeKuoD5Init,
                dim999JoeKuoD5Init,
                dim1000JoeKuoD5Init,
                dim1001JoeKuoD5Init,
                dim1002JoeKuoD5Init,
                dim1003JoeKuoD5Init,
                dim1004JoeKuoD5Init,
                dim1005JoeKuoD5Init,
                dim1006JoeKuoD5Init,
                dim1007JoeKuoD5Init,
                dim1008JoeKuoD5Init,
                dim1009JoeKuoD5Init,
                dim1010JoeKuoD5Init,
                dim1011JoeKuoD5Init,
                dim1012JoeKuoD5Init,
                dim1013JoeKuoD5Init,
                dim1014JoeKuoD5Init,
                dim1015JoeKuoD5Init,
                dim1016JoeKuoD5Init,
                dim1017JoeKuoD5Init,
                dim1018JoeKuoD5Init,
                dim1019JoeKuoD5Init,
                dim1020JoeKuoD5Init,
                dim1021JoeKuoD5Init,
                dim1022JoeKuoD5Init,
                dim1023JoeKuoD5Init,
                dim1024JoeKuoD5Init,
                dim1025JoeKuoD5Init,
                dim1026JoeKuoD5Init,
                dim1027JoeKuoD5Init,
                dim1028JoeKuoD5Init,
                dim1029JoeKuoD5Init,
                dim1030JoeKuoD5Init,
                dim1031JoeKuoD5Init,
                dim1032JoeKuoD5Init,
                dim1033JoeKuoD5Init,
                dim1034JoeKuoD5Init,
                dim1035JoeKuoD5Init,
                dim1036JoeKuoD5Init,
                dim1037JoeKuoD5Init,
                dim1038JoeKuoD5Init,
                dim1039JoeKuoD5Init,
                dim1040JoeKuoD5Init,
                dim1041JoeKuoD5Init,
                dim1042JoeKuoD5Init,
                dim1043JoeKuoD5Init,
                dim1044JoeKuoD5Init,
                dim1045JoeKuoD5Init,
                dim1046JoeKuoD5Init,
                dim1047JoeKuoD5Init,
                dim1048JoeKuoD5Init,
                dim1049JoeKuoD5Init,
                dim1050JoeKuoD5Init,
                dim1051JoeKuoD5Init,
                dim1052JoeKuoD5Init,
                dim1053JoeKuoD5Init,
                dim1054JoeKuoD5Init,
                dim1055JoeKuoD5Init,
                dim1056JoeKuoD5Init,
                dim1057JoeKuoD5Init,
                dim1058JoeKuoD5Init,
                dim1059JoeKuoD5Init,
                dim1060JoeKuoD5Init,
                dim1061JoeKuoD5Init,
                dim1062JoeKuoD5Init,
                dim1063JoeKuoD5Init,
                dim1064JoeKuoD5Init,
                dim1065JoeKuoD5Init,
                dim1066JoeKuoD5Init,
                dim1067JoeKuoD5Init,
                dim1068JoeKuoD5Init,
                dim1069JoeKuoD5Init,
                dim1070JoeKuoD5Init,
                dim1071JoeKuoD5Init,
                dim1072JoeKuoD5Init,
                dim1073JoeKuoD5Init,
                dim1074JoeKuoD5Init,
                dim1075JoeKuoD5Init,
                dim1076JoeKuoD5Init,
                dim1077JoeKuoD5Init,
                dim1078JoeKuoD5Init,
                dim1079JoeKuoD5Init,
                dim1080JoeKuoD5Init,
                dim1081JoeKuoD5Init,
                dim1082JoeKuoD5Init,
                dim1083JoeKuoD5Init,
                dim1084JoeKuoD5Init,
                dim1085JoeKuoD5Init,
                dim1086JoeKuoD5Init,
                dim1087JoeKuoD5Init,
                dim1088JoeKuoD5Init,
                dim1089JoeKuoD5Init,
                dim1090JoeKuoD5Init,
                dim1091JoeKuoD5Init,
                dim1092JoeKuoD5Init,
                dim1093JoeKuoD5Init,
                dim1094JoeKuoD5Init,
                dim1095JoeKuoD5Init,
                dim1096JoeKuoD5Init,
                dim1097JoeKuoD5Init,
                dim1098JoeKuoD5Init,
                dim1099JoeKuoD5Init,
                dim1100JoeKuoD5Init,
                dim1101JoeKuoD5Init,
                dim1102JoeKuoD5Init,
                dim1103JoeKuoD5Init,
                dim1104JoeKuoD5Init,
                dim1105JoeKuoD5Init,
                dim1106JoeKuoD5Init,
                dim1107JoeKuoD5Init,
                dim1108JoeKuoD5Init,
                dim1109JoeKuoD5Init,
                dim1110JoeKuoD5Init,
                dim1111JoeKuoD5Init,
                dim1112JoeKuoD5Init,
                dim1113JoeKuoD5Init,
                dim1114JoeKuoD5Init,
                dim1115JoeKuoD5Init,
                dim1116JoeKuoD5Init,
                dim1117JoeKuoD5Init,
                dim1118JoeKuoD5Init,
                dim1119JoeKuoD5Init,
                dim1120JoeKuoD5Init,
                dim1121JoeKuoD5Init,
                dim1122JoeKuoD5Init,
                dim1123JoeKuoD5Init,
                dim1124JoeKuoD5Init,
                dim1125JoeKuoD5Init,
                dim1126JoeKuoD5Init,
                dim1127JoeKuoD5Init,
                dim1128JoeKuoD5Init,
                dim1129JoeKuoD5Init,
                dim1130JoeKuoD5Init,
                dim1131JoeKuoD5Init,
                dim1132JoeKuoD5Init,
                dim1133JoeKuoD5Init,
                dim1134JoeKuoD5Init,
                dim1135JoeKuoD5Init,
                dim1136JoeKuoD5Init,
                dim1137JoeKuoD5Init,
                dim1138JoeKuoD5Init,
                dim1139JoeKuoD5Init,
                dim1140JoeKuoD5Init,
                dim1141JoeKuoD5Init,
                dim1142JoeKuoD5Init,
                dim1143JoeKuoD5Init,
                dim1144JoeKuoD5Init,
                dim1145JoeKuoD5Init,
                dim1146JoeKuoD5Init,
                dim1147JoeKuoD5Init,
                dim1148JoeKuoD5Init,
                dim1149JoeKuoD5Init,
                dim1150JoeKuoD5Init,
                dim1151JoeKuoD5Init,
                dim1152JoeKuoD5Init,
                dim1153JoeKuoD5Init,
                dim1154JoeKuoD5Init,
                dim1155JoeKuoD5Init,
                dim1156JoeKuoD5Init,
                dim1157JoeKuoD5Init,
                dim1158JoeKuoD5Init,
                dim1159JoeKuoD5Init,
                dim1160JoeKuoD5Init,
                dim1161JoeKuoD5Init,
                dim1162JoeKuoD5Init,
                dim1163JoeKuoD5Init,
                dim1164JoeKuoD5Init,
                dim1165JoeKuoD5Init,
                dim1166JoeKuoD5Init,
                dim1167JoeKuoD5Init,
                dim1168JoeKuoD5Init,
                dim1169JoeKuoD5Init,
                dim1170JoeKuoD5Init,
                dim1171JoeKuoD5Init,
                dim1172JoeKuoD5Init,
                dim1173JoeKuoD5Init,
                dim1174JoeKuoD5Init,
                dim1175JoeKuoD5Init,
                dim1176JoeKuoD5Init,
                dim1177JoeKuoD5Init,
                dim1178JoeKuoD5Init,
                dim1179JoeKuoD5Init,
                dim1180JoeKuoD5Init,
                dim1181JoeKuoD5Init,
                dim1182JoeKuoD5Init,
                dim1183JoeKuoD5Init,
                dim1184JoeKuoD5Init,
                dim1185JoeKuoD5Init,
                dim1186JoeKuoD5Init,
                dim1187JoeKuoD5Init,
                dim1188JoeKuoD5Init,
                dim1189JoeKuoD5Init,
                dim1190JoeKuoD5Init,
                dim1191JoeKuoD5Init,
                dim1192JoeKuoD5Init,
                dim1193JoeKuoD5Init,
                dim1194JoeKuoD5Init,
                dim1195JoeKuoD5Init,
                dim1196JoeKuoD5Init,
                dim1197JoeKuoD5Init,
                dim1198JoeKuoD5Init,
                dim1199JoeKuoD5Init,
                dim1200JoeKuoD5Init,
                dim1201JoeKuoD5Init,
                dim1202JoeKuoD5Init,
                dim1203JoeKuoD5Init,
                dim1204JoeKuoD5Init,
                dim1205JoeKuoD5Init,
                dim1206JoeKuoD5Init,
                dim1207JoeKuoD5Init,
                dim1208JoeKuoD5Init,
                dim1209JoeKuoD5Init,
                dim1210JoeKuoD5Init,
                dim1211JoeKuoD5Init,
                dim1212JoeKuoD5Init,
                dim1213JoeKuoD5Init,
                dim1214JoeKuoD5Init,
                dim1215JoeKuoD5Init,
                dim1216JoeKuoD5Init,
                dim1217JoeKuoD5Init,
                dim1218JoeKuoD5Init,
                dim1219JoeKuoD5Init,
                dim1220JoeKuoD5Init,
                dim1221JoeKuoD5Init,
                dim1222JoeKuoD5Init,
                dim1223JoeKuoD5Init,
                dim1224JoeKuoD5Init,
                dim1225JoeKuoD5Init,
                dim1226JoeKuoD5Init,
                dim1227JoeKuoD5Init,
                dim1228JoeKuoD5Init,
                dim1229JoeKuoD5Init,
                dim1230JoeKuoD5Init,
                dim1231JoeKuoD5Init,
                dim1232JoeKuoD5Init,
                dim1233JoeKuoD5Init,
                dim1234JoeKuoD5Init,
                dim1235JoeKuoD5Init,
                dim1236JoeKuoD5Init,
                dim1237JoeKuoD5Init,
                dim1238JoeKuoD5Init,
                dim1239JoeKuoD5Init,
                dim1240JoeKuoD5Init,
                dim1241JoeKuoD5Init,
                dim1242JoeKuoD5Init,
                dim1243JoeKuoD5Init,
                dim1244JoeKuoD5Init,
                dim1245JoeKuoD5Init,
                dim1246JoeKuoD5Init,
                dim1247JoeKuoD5Init,
                dim1248JoeKuoD5Init,
                dim1249JoeKuoD5Init,
                dim1250JoeKuoD5Init,
                dim1251JoeKuoD5Init,
                dim1252JoeKuoD5Init,
                dim1253JoeKuoD5Init,
                dim1254JoeKuoD5Init,
                dim1255JoeKuoD5Init,
                dim1256JoeKuoD5Init,
                dim1257JoeKuoD5Init,
                dim1258JoeKuoD5Init,
                dim1259JoeKuoD5Init,
                dim1260JoeKuoD5Init,
                dim1261JoeKuoD5Init,
                dim1262JoeKuoD5Init,
                dim1263JoeKuoD5Init,
                dim1264JoeKuoD5Init,
                dim1265JoeKuoD5Init,
                dim1266JoeKuoD5Init,
                dim1267JoeKuoD5Init,
                dim1268JoeKuoD5Init,
                dim1269JoeKuoD5Init,
                dim1270JoeKuoD5Init,
                dim1271JoeKuoD5Init,
                dim1272JoeKuoD5Init,
                dim1273JoeKuoD5Init,
                dim1274JoeKuoD5Init,
                dim1275JoeKuoD5Init,
                dim1276JoeKuoD5Init,
                dim1277JoeKuoD5Init,
                dim1278JoeKuoD5Init,
                dim1279JoeKuoD5Init,
                dim1280JoeKuoD5Init,
                dim1281JoeKuoD5Init,
                dim1282JoeKuoD5Init,
                dim1283JoeKuoD5Init,
                dim1284JoeKuoD5Init,
                dim1285JoeKuoD5Init,
                dim1286JoeKuoD5Init,
                dim1287JoeKuoD5Init,
                dim1288JoeKuoD5Init,
                dim1289JoeKuoD5Init,
                dim1290JoeKuoD5Init,
                dim1291JoeKuoD5Init,
                dim1292JoeKuoD5Init,
                dim1293JoeKuoD5Init,
                dim1294JoeKuoD5Init,
                dim1295JoeKuoD5Init,
                dim1296JoeKuoD5Init,
                dim1297JoeKuoD5Init,
                dim1298JoeKuoD5Init,
                dim1299JoeKuoD5Init,
                dim1300JoeKuoD5Init,
                dim1301JoeKuoD5Init,
                dim1302JoeKuoD5Init,
                dim1303JoeKuoD5Init,
                dim1304JoeKuoD5Init,
                dim1305JoeKuoD5Init,
                dim1306JoeKuoD5Init,
                dim1307JoeKuoD5Init,
                dim1308JoeKuoD5Init,
                dim1309JoeKuoD5Init,
                dim1310JoeKuoD5Init,
                dim1311JoeKuoD5Init,
                dim1312JoeKuoD5Init,
                dim1313JoeKuoD5Init,
                dim1314JoeKuoD5Init,
                dim1315JoeKuoD5Init,
                dim1316JoeKuoD5Init,
                dim1317JoeKuoD5Init,
                dim1318JoeKuoD5Init,
                dim1319JoeKuoD5Init,
                dim1320JoeKuoD5Init,
                dim1321JoeKuoD5Init,
                dim1322JoeKuoD5Init,
                dim1323JoeKuoD5Init,
                dim1324JoeKuoD5Init,
                dim1325JoeKuoD5Init,
                dim1326JoeKuoD5Init,
                dim1327JoeKuoD5Init,
                dim1328JoeKuoD5Init,
                dim1329JoeKuoD5Init,
                dim1330JoeKuoD5Init,
                dim1331JoeKuoD5Init,
                dim1332JoeKuoD5Init,
                dim1333JoeKuoD5Init,
                dim1334JoeKuoD5Init,
                dim1335JoeKuoD5Init,
                dim1336JoeKuoD5Init,
                dim1337JoeKuoD5Init,
                dim1338JoeKuoD5Init,
                dim1339JoeKuoD5Init,
                dim1340JoeKuoD5Init,
                dim1341JoeKuoD5Init,
                dim1342JoeKuoD5Init,
                dim1343JoeKuoD5Init,
                dim1344JoeKuoD5Init,
                dim1345JoeKuoD5Init,
                dim1346JoeKuoD5Init,
                dim1347JoeKuoD5Init,
                dim1348JoeKuoD5Init,
                dim1349JoeKuoD5Init,
                dim1350JoeKuoD5Init,
                dim1351JoeKuoD5Init,
                dim1352JoeKuoD5Init,
                dim1353JoeKuoD5Init,
                dim1354JoeKuoD5Init,
                dim1355JoeKuoD5Init,
                dim1356JoeKuoD5Init,
                dim1357JoeKuoD5Init,
                dim1358JoeKuoD5Init,
                dim1359JoeKuoD5Init,
                dim1360JoeKuoD5Init,
                dim1361JoeKuoD5Init,
                dim1362JoeKuoD5Init,
                dim1363JoeKuoD5Init,
                dim1364JoeKuoD5Init,
                dim1365JoeKuoD5Init,
                dim1366JoeKuoD5Init,
                dim1367JoeKuoD5Init,
                dim1368JoeKuoD5Init,
                dim1369JoeKuoD5Init,
                dim1370JoeKuoD5Init,
                dim1371JoeKuoD5Init,
                dim1372JoeKuoD5Init,
                dim1373JoeKuoD5Init,
                dim1374JoeKuoD5Init,
                dim1375JoeKuoD5Init,
                dim1376JoeKuoD5Init,
                dim1377JoeKuoD5Init,
                dim1378JoeKuoD5Init,
                dim1379JoeKuoD5Init,
                dim1380JoeKuoD5Init,
                dim1381JoeKuoD5Init,
                dim1382JoeKuoD5Init,
                dim1383JoeKuoD5Init,
                dim1384JoeKuoD5Init,
                dim1385JoeKuoD5Init,
                dim1386JoeKuoD5Init,
                dim1387JoeKuoD5Init,
                dim1388JoeKuoD5Init,
                dim1389JoeKuoD5Init,
                dim1390JoeKuoD5Init,
                dim1391JoeKuoD5Init,
                dim1392JoeKuoD5Init,
                dim1393JoeKuoD5Init,
                dim1394JoeKuoD5Init,
                dim1395JoeKuoD5Init,
                dim1396JoeKuoD5Init,
                dim1397JoeKuoD5Init,
                dim1398JoeKuoD5Init,
                dim1399JoeKuoD5Init,
                dim1400JoeKuoD5Init,
                dim1401JoeKuoD5Init,
                dim1402JoeKuoD5Init,
                dim1403JoeKuoD5Init,
                dim1404JoeKuoD5Init,
                dim1405JoeKuoD5Init,
                dim1406JoeKuoD5Init,
                dim1407JoeKuoD5Init,
                dim1408JoeKuoD5Init,
                dim1409JoeKuoD5Init,
                dim1410JoeKuoD5Init,
                dim1411JoeKuoD5Init,
                dim1412JoeKuoD5Init,
                dim1413JoeKuoD5Init,
                dim1414JoeKuoD5Init,
                dim1415JoeKuoD5Init,
                dim1416JoeKuoD5Init,
                dim1417JoeKuoD5Init,
                dim1418JoeKuoD5Init,
                dim1419JoeKuoD5Init,
                dim1420JoeKuoD5Init,
                dim1421JoeKuoD5Init,
                dim1422JoeKuoD5Init,
                dim1423JoeKuoD5Init,
                dim1424JoeKuoD5Init,
                dim1425JoeKuoD5Init,
                dim1426JoeKuoD5Init,
                dim1427JoeKuoD5Init,
                dim1428JoeKuoD5Init,
                dim1429JoeKuoD5Init,
                dim1430JoeKuoD5Init,
                dim1431JoeKuoD5Init,
                dim1432JoeKuoD5Init,
                dim1433JoeKuoD5Init,
                dim1434JoeKuoD5Init,
                dim1435JoeKuoD5Init,
                dim1436JoeKuoD5Init,
                dim1437JoeKuoD5Init,
                dim1438JoeKuoD5Init,
                dim1439JoeKuoD5Init,
                dim1440JoeKuoD5Init,
                dim1441JoeKuoD5Init,
                dim1442JoeKuoD5Init,
                dim1443JoeKuoD5Init,
                dim1444JoeKuoD5Init,
                dim1445JoeKuoD5Init,
                dim1446JoeKuoD5Init,
                dim1447JoeKuoD5Init,
                dim1448JoeKuoD5Init,
                dim1449JoeKuoD5Init,
                dim1450JoeKuoD5Init,
                dim1451JoeKuoD5Init,
                dim1452JoeKuoD5Init,
                dim1453JoeKuoD5Init,
                dim1454JoeKuoD5Init,
                dim1455JoeKuoD5Init,
                dim1456JoeKuoD5Init,
                dim1457JoeKuoD5Init,
                dim1458JoeKuoD5Init,
                dim1459JoeKuoD5Init,
                dim1460JoeKuoD5Init,
                dim1461JoeKuoD5Init,
                dim1462JoeKuoD5Init,
                dim1463JoeKuoD5Init,
                dim1464JoeKuoD5Init,
                dim1465JoeKuoD5Init,
                dim1466JoeKuoD5Init,
                dim1467JoeKuoD5Init,
                dim1468JoeKuoD5Init,
                dim1469JoeKuoD5Init,
                dim1470JoeKuoD5Init,
                dim1471JoeKuoD5Init,
                dim1472JoeKuoD5Init,
                dim1473JoeKuoD5Init,
                dim1474JoeKuoD5Init,
                dim1475JoeKuoD5Init,
                dim1476JoeKuoD5Init,
                dim1477JoeKuoD5Init,
                dim1478JoeKuoD5Init,
                dim1479JoeKuoD5Init,
                dim1480JoeKuoD5Init,
                dim1481JoeKuoD5Init,
                dim1482JoeKuoD5Init,
                dim1483JoeKuoD5Init,
                dim1484JoeKuoD5Init,
                dim1485JoeKuoD5Init,
                dim1486JoeKuoD5Init,
                dim1487JoeKuoD5Init,
                dim1488JoeKuoD5Init,
                dim1489JoeKuoD5Init,
                dim1490JoeKuoD5Init,
                dim1491JoeKuoD5Init,
                dim1492JoeKuoD5Init,
                dim1493JoeKuoD5Init,
                dim1494JoeKuoD5Init,
                dim1495JoeKuoD5Init,
                dim1496JoeKuoD5Init,
                dim1497JoeKuoD5Init,
                dim1498JoeKuoD5Init,
                dim1499JoeKuoD5Init,
                dim1500JoeKuoD5Init,
                dim1501JoeKuoD5Init,
                dim1502JoeKuoD5Init,
                dim1503JoeKuoD5Init,
                dim1504JoeKuoD5Init,
                dim1505JoeKuoD5Init,
                dim1506JoeKuoD5Init,
                dim1507JoeKuoD5Init,
                dim1508JoeKuoD5Init,
                dim1509JoeKuoD5Init,
                dim1510JoeKuoD5Init,
                dim1511JoeKuoD5Init,
                dim1512JoeKuoD5Init,
                dim1513JoeKuoD5Init,
                dim1514JoeKuoD5Init,
                dim1515JoeKuoD5Init,
                dim1516JoeKuoD5Init,
                dim1517JoeKuoD5Init,
                dim1518JoeKuoD5Init,
                dim1519JoeKuoD5Init,
                dim1520JoeKuoD5Init,
                dim1521JoeKuoD5Init,
                dim1522JoeKuoD5Init,
                dim1523JoeKuoD5Init,
                dim1524JoeKuoD5Init,
                dim1525JoeKuoD5Init,
                dim1526JoeKuoD5Init,
                dim1527JoeKuoD5Init,
                dim1528JoeKuoD5Init,
                dim1529JoeKuoD5Init,
                dim1530JoeKuoD5Init,
                dim1531JoeKuoD5Init,
                dim1532JoeKuoD5Init,
                dim1533JoeKuoD5Init,
                dim1534JoeKuoD5Init,
                dim1535JoeKuoD5Init,
                dim1536JoeKuoD5Init,
                dim1537JoeKuoD5Init,
                dim1538JoeKuoD5Init,
                dim1539JoeKuoD5Init,
                dim1540JoeKuoD5Init,
                dim1541JoeKuoD5Init,
                dim1542JoeKuoD5Init,
                dim1543JoeKuoD5Init,
                dim1544JoeKuoD5Init,
                dim1545JoeKuoD5Init,
                dim1546JoeKuoD5Init,
                dim1547JoeKuoD5Init,
                dim1548JoeKuoD5Init,
                dim1549JoeKuoD5Init,
                dim1550JoeKuoD5Init,
                dim1551JoeKuoD5Init,
                dim1552JoeKuoD5Init,
                dim1553JoeKuoD5Init,
                dim1554JoeKuoD5Init,
                dim1555JoeKuoD5Init,
                dim1556JoeKuoD5Init,
                dim1557JoeKuoD5Init,
                dim1558JoeKuoD5Init,
                dim1559JoeKuoD5Init,
                dim1560JoeKuoD5Init,
                dim1561JoeKuoD5Init,
                dim1562JoeKuoD5Init,
                dim1563JoeKuoD5Init,
                dim1564JoeKuoD5Init,
                dim1565JoeKuoD5Init,
                dim1566JoeKuoD5Init,
                dim1567JoeKuoD5Init,
                dim1568JoeKuoD5Init,
                dim1569JoeKuoD5Init,
                dim1570JoeKuoD5Init,
                dim1571JoeKuoD5Init,
                dim1572JoeKuoD5Init,
                dim1573JoeKuoD5Init,
                dim1574JoeKuoD5Init,
                dim1575JoeKuoD5Init,
                dim1576JoeKuoD5Init,
                dim1577JoeKuoD5Init,
                dim1578JoeKuoD5Init,
                dim1579JoeKuoD5Init,
                dim1580JoeKuoD5Init,
                dim1581JoeKuoD5Init,
                dim1582JoeKuoD5Init,
                dim1583JoeKuoD5Init,
                dim1584JoeKuoD5Init,
                dim1585JoeKuoD5Init,
                dim1586JoeKuoD5Init,
                dim1587JoeKuoD5Init,
                dim1588JoeKuoD5Init,
                dim1589JoeKuoD5Init,
                dim1590JoeKuoD5Init,
                dim1591JoeKuoD5Init,
                dim1592JoeKuoD5Init,
                dim1593JoeKuoD5Init,
                dim1594JoeKuoD5Init,
                dim1595JoeKuoD5Init,
                dim1596JoeKuoD5Init,
                dim1597JoeKuoD5Init,
                dim1598JoeKuoD5Init,
                dim1599JoeKuoD5Init,
                dim1600JoeKuoD5Init,
                dim1601JoeKuoD5Init,
                dim1602JoeKuoD5Init,
                dim1603JoeKuoD5Init,
                dim1604JoeKuoD5Init,
                dim1605JoeKuoD5Init,
                dim1606JoeKuoD5Init,
                dim1607JoeKuoD5Init,
                dim1608JoeKuoD5Init,
                dim1609JoeKuoD5Init,
                dim1610JoeKuoD5Init,
                dim1611JoeKuoD5Init,
                dim1612JoeKuoD5Init,
                dim1613JoeKuoD5Init,
                dim1614JoeKuoD5Init,
                dim1615JoeKuoD5Init,
                dim1616JoeKuoD5Init,
                dim1617JoeKuoD5Init,
                dim1618JoeKuoD5Init,
                dim1619JoeKuoD5Init,
                dim1620JoeKuoD5Init,
                dim1621JoeKuoD5Init,
                dim1622JoeKuoD5Init,
                dim1623JoeKuoD5Init,
                dim1624JoeKuoD5Init,
                dim1625JoeKuoD5Init,
                dim1626JoeKuoD5Init,
                dim1627JoeKuoD5Init,
                dim1628JoeKuoD5Init,
                dim1629JoeKuoD5Init,
                dim1630JoeKuoD5Init,
                dim1631JoeKuoD5Init,
                dim1632JoeKuoD5Init,
                dim1633JoeKuoD5Init,
                dim1634JoeKuoD5Init,
                dim1635JoeKuoD5Init,
                dim1636JoeKuoD5Init,
                dim1637JoeKuoD5Init,
                dim1638JoeKuoD5Init,
                dim1639JoeKuoD5Init,
                dim1640JoeKuoD5Init,
                dim1641JoeKuoD5Init,
                dim1642JoeKuoD5Init,
                dim1643JoeKuoD5Init,
                dim1644JoeKuoD5Init,
                dim1645JoeKuoD5Init,
                dim1646JoeKuoD5Init,
                dim1647JoeKuoD5Init,
                dim1648JoeKuoD5Init,
                dim1649JoeKuoD5Init,
                dim1650JoeKuoD5Init,
                dim1651JoeKuoD5Init,
                dim1652JoeKuoD5Init,
                dim1653JoeKuoD5Init,
                dim1654JoeKuoD5Init,
                dim1655JoeKuoD5Init,
                dim1656JoeKuoD5Init,
                dim1657JoeKuoD5Init,
                dim1658JoeKuoD5Init,
                dim1659JoeKuoD5Init,
                dim1660JoeKuoD5Init,
                dim1661JoeKuoD5Init,
                dim1662JoeKuoD5Init,
                dim1663JoeKuoD5Init,
                dim1664JoeKuoD5Init,
                dim1665JoeKuoD5Init,
                dim1666JoeKuoD5Init,
                dim1667JoeKuoD5Init,
                dim1668JoeKuoD5Init,
                dim1669JoeKuoD5Init,
                dim1670JoeKuoD5Init,
                dim1671JoeKuoD5Init,
                dim1672JoeKuoD5Init,
                dim1673JoeKuoD5Init,
                dim1674JoeKuoD5Init,
                dim1675JoeKuoD5Init,
                dim1676JoeKuoD5Init,
                dim1677JoeKuoD5Init,
                dim1678JoeKuoD5Init,
                dim1679JoeKuoD5Init,
                dim1680JoeKuoD5Init,
                dim1681JoeKuoD5Init,
                dim1682JoeKuoD5Init,
                dim1683JoeKuoD5Init,
                dim1684JoeKuoD5Init,
                dim1685JoeKuoD5Init,
                dim1686JoeKuoD5Init,
                dim1687JoeKuoD5Init,
                dim1688JoeKuoD5Init,
                dim1689JoeKuoD5Init,
                dim1690JoeKuoD5Init,
                dim1691JoeKuoD5Init,
                dim1692JoeKuoD5Init,
                dim1693JoeKuoD5Init,
                dim1694JoeKuoD5Init,
                dim1695JoeKuoD5Init,
                dim1696JoeKuoD5Init,
                dim1697JoeKuoD5Init,
                dim1698JoeKuoD5Init,
                dim1699JoeKuoD5Init,
                dim1700JoeKuoD5Init,
                dim1701JoeKuoD5Init,
                dim1702JoeKuoD5Init,
                dim1703JoeKuoD5Init,
                dim1704JoeKuoD5Init,
                dim1705JoeKuoD5Init,
                dim1706JoeKuoD5Init,
                dim1707JoeKuoD5Init,
                dim1708JoeKuoD5Init,
                dim1709JoeKuoD5Init,
                dim1710JoeKuoD5Init,
                dim1711JoeKuoD5Init,
                dim1712JoeKuoD5Init,
                dim1713JoeKuoD5Init,
                dim1714JoeKuoD5Init,
                dim1715JoeKuoD5Init,
                dim1716JoeKuoD5Init,
                dim1717JoeKuoD5Init,
                dim1718JoeKuoD5Init,
                dim1719JoeKuoD5Init,
                dim1720JoeKuoD5Init,
                dim1721JoeKuoD5Init,
                dim1722JoeKuoD5Init,
                dim1723JoeKuoD5Init,
                dim1724JoeKuoD5Init,
                dim1725JoeKuoD5Init,
                dim1726JoeKuoD5Init,
                dim1727JoeKuoD5Init,
                dim1728JoeKuoD5Init,
                dim1729JoeKuoD5Init,
                dim1730JoeKuoD5Init,
                dim1731JoeKuoD5Init,
                dim1732JoeKuoD5Init,
                dim1733JoeKuoD5Init,
                dim1734JoeKuoD5Init,
                dim1735JoeKuoD5Init,
                dim1736JoeKuoD5Init,
                dim1737JoeKuoD5Init,
                dim1738JoeKuoD5Init,
                dim1739JoeKuoD5Init,
                dim1740JoeKuoD5Init,
                dim1741JoeKuoD5Init,
                dim1742JoeKuoD5Init,
                dim1743JoeKuoD5Init,
                dim1744JoeKuoD5Init,
                dim1745JoeKuoD5Init,
                dim1746JoeKuoD5Init,
                dim1747JoeKuoD5Init,
                dim1748JoeKuoD5Init,
                dim1749JoeKuoD5Init,
                dim1750JoeKuoD5Init,
                dim1751JoeKuoD5Init,
                dim1752JoeKuoD5Init,
                dim1753JoeKuoD5Init,
                dim1754JoeKuoD5Init,
                dim1755JoeKuoD5Init,
                dim1756JoeKuoD5Init,
                dim1757JoeKuoD5Init,
                dim1758JoeKuoD5Init,
                dim1759JoeKuoD5Init,
                dim1760JoeKuoD5Init,
                dim1761JoeKuoD5Init,
                dim1762JoeKuoD5Init,
                dim1763JoeKuoD5Init,
                dim1764JoeKuoD5Init,
                dim1765JoeKuoD5Init,
                dim1766JoeKuoD5Init,
                dim1767JoeKuoD5Init,
                dim1768JoeKuoD5Init,
                dim1769JoeKuoD5Init,
                dim1770JoeKuoD5Init,
                dim1771JoeKuoD5Init,
                dim1772JoeKuoD5Init,
                dim1773JoeKuoD5Init,
                dim1774JoeKuoD5Init,
                dim1775JoeKuoD5Init,
                dim1776JoeKuoD5Init,
                dim1777JoeKuoD5Init,
                dim1778JoeKuoD5Init,
                dim1779JoeKuoD5Init,
                dim1780JoeKuoD5Init,
                dim1781JoeKuoD5Init,
                dim1782JoeKuoD5Init,
                dim1783JoeKuoD5Init,
                dim1784JoeKuoD5Init,
                dim1785JoeKuoD5Init,
                dim1786JoeKuoD5Init,
                dim1787JoeKuoD5Init,
                dim1788JoeKuoD5Init,
                dim1789JoeKuoD5Init,
                dim1790JoeKuoD5Init,
                dim1791JoeKuoD5Init,
                dim1792JoeKuoD5Init,
                dim1793JoeKuoD5Init,
                dim1794JoeKuoD5Init,
                dim1795JoeKuoD5Init,
                dim1796JoeKuoD5Init,
                dim1797JoeKuoD5Init,
                dim1798JoeKuoD5Init,
                dim1799JoeKuoD5Init,
                dim1800JoeKuoD5Init,
                dim1801JoeKuoD5Init,
                dim1802JoeKuoD5Init,
                dim1803JoeKuoD5Init,
                dim1804JoeKuoD5Init,
                dim1805JoeKuoD5Init,
                dim1806JoeKuoD5Init,
                dim1807JoeKuoD5Init,
                dim1808JoeKuoD5Init,
                dim1809JoeKuoD5Init,
                dim1810JoeKuoD5Init,
                dim1811JoeKuoD5Init,
                dim1812JoeKuoD5Init,
                dim1813JoeKuoD5Init,
                dim1814JoeKuoD5Init,
                dim1815JoeKuoD5Init,
                dim1816JoeKuoD5Init,
                dim1817JoeKuoD5Init,
                dim1818JoeKuoD5Init,
                dim1819JoeKuoD5Init,
                dim1820JoeKuoD5Init,
                dim1821JoeKuoD5Init,
                dim1822JoeKuoD5Init,
                dim1823JoeKuoD5Init,
                dim1824JoeKuoD5Init,
                dim1825JoeKuoD5Init,
                dim1826JoeKuoD5Init,
                dim1827JoeKuoD5Init,
                dim1828JoeKuoD5Init,
                dim1829JoeKuoD5Init,
                dim1830JoeKuoD5Init,
                dim1831JoeKuoD5Init,
                dim1832JoeKuoD5Init,
                dim1833JoeKuoD5Init,
                dim1834JoeKuoD5Init,
                dim1835JoeKuoD5Init,
                dim1836JoeKuoD5Init,
                dim1837JoeKuoD5Init,
                dim1838JoeKuoD5Init,
                dim1839JoeKuoD5Init,
                dim1840JoeKuoD5Init,
                dim1841JoeKuoD5Init,
                dim1842JoeKuoD5Init,
                dim1843JoeKuoD5Init,
                dim1844JoeKuoD5Init,
                dim1845JoeKuoD5Init,
                dim1846JoeKuoD5Init,
                dim1847JoeKuoD5Init,
                dim1848JoeKuoD5Init,
                dim1849JoeKuoD5Init,
                dim1850JoeKuoD5Init,
                dim1851JoeKuoD5Init,
                dim1852JoeKuoD5Init,
                dim1853JoeKuoD5Init,
                dim1854JoeKuoD5Init,
                dim1855JoeKuoD5Init,
                dim1856JoeKuoD5Init,
                dim1857JoeKuoD5Init,
                dim1858JoeKuoD5Init,
                dim1859JoeKuoD5Init,
                dim1860JoeKuoD5Init,
                dim1861JoeKuoD5Init,
                dim1862JoeKuoD5Init,
                dim1863JoeKuoD5Init,
                dim1864JoeKuoD5Init,
                dim1865JoeKuoD5Init,
                dim1866JoeKuoD5Init,
                dim1867JoeKuoD5Init,
                dim1868JoeKuoD5Init,
                dim1869JoeKuoD5Init,
                dim1870JoeKuoD5Init,
                dim1871JoeKuoD5Init,
                dim1872JoeKuoD5Init,
                dim1873JoeKuoD5Init,
                dim1874JoeKuoD5Init,
                dim1875JoeKuoD5Init,
                dim1876JoeKuoD5Init,
                dim1877JoeKuoD5Init,
                dim1878JoeKuoD5Init,
                dim1879JoeKuoD5Init,
                dim1880JoeKuoD5Init,
                dim1881JoeKuoD5Init,
                dim1882JoeKuoD5Init,
                dim1883JoeKuoD5Init,
                dim1884JoeKuoD5Init,
                dim1885JoeKuoD5Init,
                dim1886JoeKuoD5Init,
                dim1887JoeKuoD5Init,
                dim1888JoeKuoD5Init,
                dim1889JoeKuoD5Init,
                dim1890JoeKuoD5Init,
                dim1891JoeKuoD5Init,
                dim1892JoeKuoD5Init,
                dim1893JoeKuoD5Init,
                dim1894JoeKuoD5Init,
                dim1895JoeKuoD5Init,
                dim1896JoeKuoD5Init,
                dim1897JoeKuoD5Init,
                dim1898JoeKuoD5Init,
                dim1899JoeKuoD5Init,
                dim1900JoeKuoD5Init,
                dim1901JoeKuoD5Init,
                dim1902JoeKuoD5Init,
                dim1903JoeKuoD5Init,
                dim1904JoeKuoD5Init,
                dim1905JoeKuoD5Init,
                dim1906JoeKuoD5Init,
                dim1907JoeKuoD5Init,
                dim1908JoeKuoD5Init,
                dim1909JoeKuoD5Init,
                dim1910JoeKuoD5Init,
                dim1911JoeKuoD5Init,
                dim1912JoeKuoD5Init,
                dim1913JoeKuoD5Init,
                dim1914JoeKuoD5Init,
                dim1915JoeKuoD5Init,
                dim1916JoeKuoD5Init,
                dim1917JoeKuoD5Init,
                dim1918JoeKuoD5Init,
                dim1919JoeKuoD5Init,
                dim1920JoeKuoD5Init,
                dim1921JoeKuoD5Init,
                dim1922JoeKuoD5Init,
                dim1923JoeKuoD5Init,
                dim1924JoeKuoD5Init,
                dim1925JoeKuoD5Init,
                dim1926JoeKuoD5Init,
                dim1927JoeKuoD5Init,
                dim1928JoeKuoD5Init,
                dim1929JoeKuoD5Init,
                dim1930JoeKuoD5Init,
                dim1931JoeKuoD5Init,
                dim1932JoeKuoD5Init,
                dim1933JoeKuoD5Init,
                dim1934JoeKuoD5Init,
                dim1935JoeKuoD5Init,
                dim1936JoeKuoD5Init,
                dim1937JoeKuoD5Init,
                dim1938JoeKuoD5Init,
                dim1939JoeKuoD5Init,
                dim1940JoeKuoD5Init,
                dim1941JoeKuoD5Init,
                dim1942JoeKuoD5Init,
                dim1943JoeKuoD5Init,
                dim1944JoeKuoD5Init,
                dim1945JoeKuoD5Init,
                dim1946JoeKuoD5Init,
                dim1947JoeKuoD5Init,
                dim1948JoeKuoD5Init,
                dim1949JoeKuoD5Init,
                dim1950JoeKuoD5Init,
                dim1951JoeKuoD5Init,
                dim1952JoeKuoD5Init,
                dim1953JoeKuoD5Init,
                dim1954JoeKuoD5Init,
                dim1955JoeKuoD5Init,
                dim1956JoeKuoD5Init,
                dim1957JoeKuoD5Init,
                dim1958JoeKuoD5Init,
                dim1959JoeKuoD5Init,
                dim1960JoeKuoD5Init,
                dim1961JoeKuoD5Init,
                dim1962JoeKuoD5Init,
                dim1963JoeKuoD5Init,
                dim1964JoeKuoD5Init,
                dim1965JoeKuoD5Init,
                dim1966JoeKuoD5Init,
                dim1967JoeKuoD5Init,
                dim1968JoeKuoD5Init,
                dim1969JoeKuoD5Init,
                dim1970JoeKuoD5Init,
                dim1971JoeKuoD5Init,
                dim1972JoeKuoD5Init,
                dim1973JoeKuoD5Init,
                dim1974JoeKuoD5Init,
                dim1975JoeKuoD5Init,
                dim1976JoeKuoD5Init,
                dim1977JoeKuoD5Init,
                dim1978JoeKuoD5Init,
                dim1979JoeKuoD5Init,
                dim1980JoeKuoD5Init,
                dim1981JoeKuoD5Init,
                dim1982JoeKuoD5Init,
                dim1983JoeKuoD5Init,
                dim1984JoeKuoD5Init,
                dim1985JoeKuoD5Init,
                dim1986JoeKuoD5Init,
                dim1987JoeKuoD5Init,
                dim1988JoeKuoD5Init,
                dim1989JoeKuoD5Init,
                dim1990JoeKuoD5Init,
                dim1991JoeKuoD5Init,
                dim1992JoeKuoD5Init,
                dim1993JoeKuoD5Init,
                dim1994JoeKuoD5Init,
                dim1995JoeKuoD5Init,
                dim1996JoeKuoD5Init,
                dim1997JoeKuoD5Init,
                dim1998JoeKuoD5Init,
                dim1999JoeKuoD5Init
            };
    """
    # Note: For brevity, the test string for Kuo only has a few arrays and pointers.
    # The script will parse what's provided.

    mojo_kuo_init_content = generate_mojo_init_body(
        cpp_kuo_code_input,
        data_array_prefix_cxx="dim", 
        data_array_suffix_cxx="JoeKuoD5Init",
        data_array_base_mojo="dim", # Mojo variables will be self.data_dim1, self.data_dim2
        main_pointer_array_cxx="JoeKuoD5initializers"
    )

    print(mojo_kuo_init_content)
