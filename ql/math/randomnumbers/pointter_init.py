import re

def generate_pointer_initializers(dim_value, mojo_type="UInt32", mojo_var_base_name="dim"):
    """
    Generates the Mojo InlineArray initialization list for pointers.

    Args:
        dim_value (int): The value of the DIM constant.
        mojo_type (str): The Mojo base type for the UnsafePointer.
        mojo_var_base_name (str): The base name for the Mojo data variables 
                                  (e.g., "dim" for "self.dim01", "self.dim10").
                                  If you used "data_dim" for variables like "self.data_dim01",
                                  then set this to "data_dim".
    """
    output_lines = []
    output_lines.append(f"        // Assuming DIM = {dim_value}")
    output_lines.append(f"        self.pointers = InlineArray[UnsafePointer[{mojo_type}], {dim_value}](")

    for i in range(1, dim_value + 1): # Iterate from 1 to DIM (inclusive)
        # Format dimension number: dim1, dim2, ... dim9, dim10, dim11 ... dim4925
        # This tries to match the pattern from your example `self.dim02.unsafe_ptr()`
        # where single-digit numbers might have a leading zero.
        # If your actual Mojo variables are dim1, dim2... (no leading zero), then
        # dim_suffix = str(i) would be simpler.
        
        # Based on your example `self.dim01.unsafe_ptr()` for index 0,
        # it seems the C++ dim1KuoInit maps to Mojo self.dim1, dim2KuoInit to self.dim2 etc.
        # Let's assume the C++ array `Kuoinitializers` is 0-indexed and
        # `Kuoinitializers[0]` points to `dim1KuoInit`
        # `Kuoinitializers[1]` points to `dim2KuoInit`
        # ...
        # `Kuoinitializers[N-1]` points to `dimNKuoInit`
        #
        # Your Mojo example:
        # index 0 -> self.dim01.unsafe_ptr() (if we assume dim01 means the 1st dim)
        # index 1 -> self.dim02.unsafe_ptr() (if we assume dim02 means the 2nd dim)
        #
        # So, the loop variable `i` (from 1 to DIM_VALUE) represents the dimension number.
        
        # Formatting the dimension number string (e.g., "01", "02", ..., "09", "10", "11")
        # This matches your example of `self.dim01`, `self.dim02`...
        # If your actual variable names are strictly `dim1`, `dim2`, `dim10` etc., then use:
        # dim_number_str = str(i)
        
        # If your variables are dim01, dim02, ... dim09, dim10, dim11, ..., dim99, dim100
        if i < 10:
            dim_number_str = f"0{i}"
        else:
            dim_number_str = str(i)
            
        # If all your variables are data_dim1, data_dim2... (no leading zeros for numbers)
        # mojo_var_name = f"{mojo_var_base_name}{i}" 
        
        # If your variables are like dim01, dim02, ... dim09, dim10, dim11 (leading zero for <10)
        # And your mojo_var_base_name is "dim"
        mojo_var_name = f"{mojo_var_base_name}{dim_number_str}"


        line = f"            self.{mojo_var_name}.unsafe_ptr()"
        if i < dim_value: # Add comma for all but the last one
            line += ","
        # The comment should map to the variable name used
        line += f"  # index {i-1} -> {mojo_var_base_name}{dim_number_str}" 
        output_lines.append(line)

    output_lines.append("        )")
    return "\n".join(output_lines)

if __name__ == "__main__":
    # This is the crucial value. Get it from your Mojo `alias DIM: Int = 4925`
    DIM_VALUE = 4925 
    
    # The Mojo base type for the pointers
    MOJO_POINTER_BASE_TYPE = "UInt32" 
    
    # The base name for your Mojo data member variables.
    # If your Mojo variables are `self.dim01`, `self.dim02`, ..., `self.dim10`, etc., this should be "dim".
    # If they are `self.data_dim01`, `self.data_dim02`, etc., this should be "data_dim".
    # Your example `self.dim01.unsafe_ptr()` implies "dim".
    MOJO_VARIABLE_BASE_NAME = "dim" 

    mojo_code_snippet = generate_pointer_initializers(DIM_VALUE, MOJO_POINTER_BASE_TYPE, MOJO_VARIABLE_BASE_NAME)
    print(mojo_code_snippet)

    # Optional: Write to a file
    # output_snippet_file = "mojo_pointers_init_list.txt"
    # with open(output_snippet_file, "w") as f_out:
    #     f_out.write(mojo_code_snippet)
    # print(f"\n--- Snippet also written to {output_snippet_file} ---")