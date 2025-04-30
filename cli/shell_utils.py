"""
Utility functions for the onion network shell.
"""

import os
import sys
import platform


def get_terminal_size():
    """
    Get the terminal size.
    
    Returns:
        tuple: (width, height)
    """
    try:
        # For Python 3.3+
        import shutil
        columns, rows = shutil.get_terminal_size()
        return columns, rows
    except:
        # Fallback
        columns = 80
        rows = 24
        
        if platform.system() == "Windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                hstdout = kernel32.GetStdHandle(-11)
                csbi = ctypes.create_string_buffer(22)
                res = kernel32.GetConsoleScreenBufferInfo(hstdout, csbi)
                
                if res:
                    import struct
                    (_, _, _, _, _, left, top, right, bottom, _, _) = struct.unpack("hhhhHhhhhhh", csbi.raw)
                    columns = right - left + 1
                    rows = bottom - top + 1
            except:
                pass
        else:
            try:
                rows, columns = os.popen('stty size', 'r').read().split()
                columns = int(columns)
                rows = int(rows)
            except:
                pass
        
        return columns, rows


def clear_screen():
    """
    Clear the terminal screen.
    """
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def print_colored(text, color=None, end="\n"):
    """
    Print colored text in the terminal.
    
    Args:
        text (str): The text to print.
        color (str, optional): The color to use. If None, no color is used.
            Valid colors: black, red, green, yellow, blue, magenta, cyan, white.
        end (str, optional): The string to append after the text.
    """
    # ANSI escape codes for colors
    colors = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "reset": "\033[0m"
    }
    
    # Check if the terminal supports colors
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty() or platform.system() == "Windows" and not "ANSICON" in os.environ:
        # Terminal doesn't support colors
        print(text, end=end)
        return
    
    # Print colored text
    if color and color in colors:
        print(f"{colors[color]}{text}{colors['reset']}", end=end)
    else:
        print(text, end=end)


def print_logo():
    """
    Print the onion network logo.
    """
    # Get terminal width
    width, _ = get_terminal_size()
    
    # Clear the screen
    clear_screen()
    
    # Define the logo
    logo = [
        "  /$$$            /$                      /$   /$             /$                                     /$      ",
        " /$__  $          |__/                     | $$ | $            | $                                    | $      ",
        "| $  \\ $ /$$$$  /$  /$$$  /$$$$ | $$| $  /$$$  /$$$   /$  /$  /$  /$$$   /$$$$      ",
        "| $  | $| $__  $| $ /$__  $| $__  $| $ $ $ /$__  $|_  $_/  | $ | $ | $ /$__  $ /$__  $      ",
        "| $  | $| $  \\ $| $| $  \\ $| $  \\ $| $  $$| $$$$  | $    | $ | $ | $| $  \\ $| $  | $      ",
        "| $  | $| $  | $| $| $  | $| $  | $| $\\  $$| $_____/  | $ /$| $ | $ | $| $  | $| $  | $      ",
        "|  $$$/| $  | $| $|  $$$/| $  | $| $ \\  $|  $$$$  |  $$/|  $$$/$$/|  $$$/|  $$$$      ",
        " \\______/ |__/  |__/|__/ \\______/ |__/  |__/|__/  \\__/ \\_______/   \\___/   \\_____/\\___/  \\______/  \\_______/      "
    ]
    
    # Center and print the logo
    for line in logo:
        padding = max(0, (width - len(line)) // 2)
        print_colored(" " * padding + line, "cyan")
    
    # Print a tagline
    tagline = "Secure, Anonymous, Encrypted"
    padding = max(0, (width - len(tagline)) // 2)
    print()
    print_colored(" " * padding + tagline, "yellow")
    print()
    print_colored("-" * width, "blue")
    print()


def format_table(headers, rows, colors=None):
    """
    Format data as a table.
    
    Args:
        headers (list): List of column headers.
        rows (list): List of rows, where each row is a list of values.
        colors (dict, optional): Dictionary mapping column indices to colors.
            Example: {0: "red", 1: "green"}
    
    Returns:
        str: The formatted table.
    """
    if not headers or not rows:
        return ""
    
    # Calculate column widths
    col_widths = [len(str(h)) for h in headers]
    
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Format the headers
    header_line = " | ".join(str(h).ljust(w) for h, w in zip(headers, col_widths))
    separator = "-+-".join("-" * w for w in col_widths)
    
    # Format the rows
    formatted_rows = []
    for row in rows:
        formatted_row = " | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
        formatted_rows.append(formatted_row)
    
    # Combine everything
    table = [
        header_line,
        separator,
    ] + formatted_rows
    
    return "\n".join(table)


def print_table(headers, rows, colors=None):
    """
    Print a formatted table.
    
    Args:
        headers (list): List of column headers.
        rows (list): List of rows, where each row is a list of values.
        colors (dict, optional): Dictionary mapping column indices to colors.
            Example: {0: "red", 1: "green"}
    """
    table = format_table(headers, rows, colors)
    print(table)


def prompt_yes_no(prompt, default=None):
    """
    Prompt the user for a yes/no answer.
    
    Args:
        prompt (str): The prompt to display.
        default (bool, optional): The default answer if the user just presses Enter.
            If None, the user must explicitly answer.
    
    Returns:
        bool: True for yes, False for no.
    """
    if default is True:
        prompt = f"{prompt} [Y/n] "
    elif default is False:
        prompt = f"{prompt} [y/N] "
    else:
        prompt = f"{prompt} [y/n] "
    
    while True:
        answer = input(prompt).strip().lower()
        
        if not answer and default is not None:
            return default
        
        if answer in ["y", "yes"]:
            return True
        
        if answer in ["n", "no"]:
            return False
        
        print_colored("Please answer 'y' or 'n'.", "yellow")


def prompt_choice(prompt, choices, default=None):
    """
    Prompt the user to choose from a list of options.
    
    Args:
        prompt (str): The prompt to display.
        choices (list): List of choices to present to the user.
        default (int, optional): The default choice (0-based index) if the user just presses Enter.
            If None, the user must explicitly choose.
    
    Returns:
        int: The index of the chosen option.
    """
    # Display the choices
    for i, choice in enumerate(choices):
        if i == default:
            print_colored(f"{i+1}. {choice} (default)", "green")
        else:
            print_colored(f"{i+1}. {choice}", "cyan")
    
    # Prompt for the choice
    while True:
        answer = input(f"{prompt} [1-{len(choices)}]: ").strip()
        
        if not answer and default is not None:
            return default
        
        try:
            choice = int(answer) - 1
            if 0 <= choice < len(choices):
                return choice
        except ValueError:
            pass
        
        print_colored(f"Please enter a number between 1 and {len(choices)}.", "yellow")


if __name__ == "__main__":
    # Test the functions
    print_colored("Testing print_colored", "red")
    print_colored("This is in green", "green")
    print_colored("This is in blue", "blue")
    print_colored("This is in yellow", "yellow")
    
    print("\nTesting print_logo")
    print_logo()
    
    print("\nTesting print_table")
    headers = ["Name", "Age", "City"]
    rows = [
        ["Alice", 25, "New York"],
        ["Bob", 30, "Los Angeles"],
        ["Charlie", 35, "Chicago"]
    ]
    print_table(headers, rows)
    
    print("\nTesting prompt_yes_no")
    answer = prompt_yes_no("Do you like Python?", default=True)
    print(f"Answer: {answer}")
    
    print("\nTesting prompt_choice")
    choices = ["Red", "Green", "Blue"]
    choice = prompt_choice("Choose a color", choices, default=1)
    print(f"You chose: {choices[choice]}")
