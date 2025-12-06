"""
Desktop File Organizer

A Python script that automatically organizes files in a directory by categorizing them
into subfolders based on their file extensions. Supports preview mode, undo functionality,
and customizable file type configurations.

Features:
    - Automatic file categorization (Images, Documents, PDFs, Videos, etc.)
    - Preview mode to see changes before applying them
    - Undo functionality to revert the last organization
    - Customizable file type mappings via JSON configuration
    - Progress bar for visual feedback during organization
    - Duplicate filename handling

Usage:
    python File_organizer.py <folder_path> [--preview] [--undo]

Examples:
    python File_organizer.py ~/Downloads
    python File_organizer.py ~/Desktop --preview
    python File_organizer.py ~/Documents --undo
"""

# Import required libraries for file operations, JSON handling, CLI arguments, and progress bars
import os  # For file system operations (path handling, directory creation)
import shutil  # For high-level file operations (moving files)
import json  # For reading/writing configuration and undo log files
import argparse  # For parsing command-line arguments
import sys  # For system-specific parameters and functions (exit codes)
from pathlib import Path  # For modern path handling and validation
from tqdm import tqdm  # For displaying progress bars during file operations

# =============================
# CONFIGURATION MANAGEMENT
# =============================

# Default file type categories and their associated extensions
# This dictionary maps folder names to lists of file extensions
# Users can override this by creating a custom file_config.json file
DEFAULT_CONFIG = {
    "Images": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],  # Common image formats
    "Documents": [".docx", ".doc", ".txt", ".md", ".pptx", ".ppt"],  # Text and presentation files
    "PDFs": [".pdf"],  # PDF documents (separate category for easy access)
    "Videos": [".mp4", ".mov", ".avi"],  # Video file formats
    "Spreadsheets": [".xlsx", ".csv"],  # Excel and CSV files
    "Archives": [".zip", ".rar", ".7z"]  # Compressed archive formats
}

# Configuration file name for custom file type mappings
# Users can create this file to define their own categories and extensions
CONFIG_FILE = "file_config.json"


def load_config():
    """
    Load file type configuration from JSON file if it exists.
    
    This function checks if a custom configuration file exists in the current directory.
    If found, it loads the custom mappings; otherwise, it uses the DEFAULT_CONFIG.
    
    The configuration file should be a JSON object with this structure:
    {
        "CategoryName": [".ext1", ".ext2"],
        "AnotherCategory": [".ext3", ".ext4"]
    }
    
    Returns:
        dict: A dictionary mapping category names (str) to lists of file extensions (list of str)
              Example: {"Images": [".png", ".jpg"], "Documents": [".docx", ".txt"]}
    
    Example:
        >>> config = load_config()
        >>> print(config["Images"])
        ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    """
    # Check if custom configuration file exists in the current directory
    if os.path.exists(CONFIG_FILE):
        try:
            # Open and parse the JSON configuration file
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {CONFIG_FILE}. Using default configuration.")
            print(f"Error: {e}")
            return DEFAULT_CONFIG
        except Exception as e:
            print(f"Warning: Could not read {CONFIG_FILE}. Using default configuration.")
            print(f"Error: {e}")
            return DEFAULT_CONFIG
    
    # If no custom config exists, return the default configuration
    return DEFAULT_CONFIG


def get_unique_filename(target_folder, filename):
    """
    Generate a unique filename if a file with the same name already exists.
    
    This function handles duplicate filenames by appending an incrementing counter
    to the base filename until a unique name is found.
    
    Args:
        target_folder (str): The folder where the file will be moved
        filename (str): The original filename
    
    Returns:
        str: A unique filename that doesn't conflict with existing files
             Examples: "photo.jpg" -> "photo_1.jpg" -> "photo_2.jpg"
    
    Example:
        >>> get_unique_filename("/Downloads/Images", "photo.jpg")
        "photo_1.jpg"  # If photo.jpg already exists
    """
    target_path = os.path.join(target_folder, filename)
    
    # If file doesn't exist, return original filename
    if not os.path.exists(target_path):
        return filename
    
    # Split filename into base name and extension
    base, extension = os.path.splitext(filename)
    counter = 1
    
    # Keep incrementing counter until we find a unique filename
    while os.path.exists(target_path):
        new_filename = f"{base}_{counter}{extension}"
        target_path = os.path.join(target_folder, new_filename)
        counter += 1
    
    return os.path.basename(target_path)


# =============================
# FILE ORGANIZATION LOGIC
# =============================

def organize_files(folder_path, preview=False):
    """
    Organize files in a folder by moving them into category-based subfolders.
    
    This is the main function that performs the file organization. It scans the specified
    folder, categorizes each file based on its extension, and moves files into appropriate
    subfolders. Files that don't match any category are moved to an "Others" folder.
    
    The function supports two modes:
    1. Normal mode: Actually moves files and saves an undo log
    2. Preview mode: Shows what would happen without making any changes
    
    Args:
        folder_path (str): Absolute or relative path to the folder to organize
                          Example: "C:/Users/John/Downloads" or "~/Desktop"
        preview (bool): If True, simulates the organization without moving files.
                       Useful for checking what will happen before committing changes.
                       Default: False
    
    Returns:
        None: This function doesn't return a value but prints status messages
    
    Side Effects:
        - Creates category subfolders within the target folder
        - Moves files from the root folder into category subfolders
        - Creates an undo log file (undo_log.json) if not in preview mode
        - Prints progress information to the console
    
    Example:
        >>> organize_files("~/Downloads", preview=True)
        Scanning folder: ~/Downloads
        Organizing: 100%|████████████| 50/50 [00:00<00:00, 250.00it/s]
        Preview complete. No files were moved.
        
        >>> organize_files("~/Downloads")
        Scanning folder: ~/Downloads
        Organizing: 100%|████████████| 50/50 [00:02<00:00, 25.00it/s]
        Undo log saved.
        File organization completed.
    """
    # Validate the folder path exists and is a directory
    folder_path = os.path.expanduser(folder_path)  # Expand ~ to home directory
    if not os.path.exists(folder_path):
        print(f"Error: The path '{folder_path}' does not exist.")
        sys.exit(1)
    
    if not os.path.isdir(folder_path):
        print(f"Error: The path '{folder_path}' is not a directory.")
        sys.exit(1)
    
    # Load file type configuration (either custom or default)
    file_types = load_config()
    
    # Initialize list to track all file movements for undo functionality
    # Each entry will be a tuple: (original_path, new_path)
    moved_files = []
    
    # Track statistics for summary
    stats = {"categorized": 0, "others": 0, "errors": 0}

    # Display the folder being scanned
    print("Scanning folder:", folder_path)
    
    try:
        # Get list of all files (not directories) in the target folder
        # This list comprehension filters out subdirectories and only includes files
        files = [
            f for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f))
        ]
    except PermissionError:
        print(f"Error: Permission denied to access '{folder_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not read directory '{folder_path}': {e}")
        sys.exit(1)
    
    if not files:
        print("No files found to organize.")
        return

    print(f"Found {len(files)} file(s) to organize.\n")
    
    # In preview mode, show detailed list of planned moves
    if preview:
        print("=== PREVIEW MODE - Planned file movements ===\n")

    # Process each file with a progress bar using tqdm
    # tqdm wraps the iterable and displays a progress bar with percentage and speed
    for filename in tqdm(files, desc="Organizing", disable=preview):
        # Construct the full path to the current file
        file_path = os.path.join(folder_path, filename)
        
        # Extract file extension and convert to lowercase for case-insensitive comparison
        # os.path.splitext returns a tuple: (filename_without_ext, extension)
        # Example: "photo.JPG" -> ("photo", ".JPG") -> ext = ".jpg"
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        # Flag to track if the file was categorized and moved
        moved = False

        # Iterate through each category and its associated extensions
        # Example: category="Images", extensions=[".png", ".jpg", ".jpeg"]
        for category, extensions in file_types.items():
            # Check if the current file's extension matches this category
            if ext in extensions:
                try:
                    # Construct the path for the category subfolder
                    # Example: "C:/Users/John/Downloads/Images"
                    target_folder = os.path.join(folder_path, category)
                    
                    # Create the category folder if it doesn't exist (only in non-preview mode)
                    if not preview:
                        os.makedirs(target_folder, exist_ok=True)

                    # Get unique filename to handle duplicates
                    unique_filename = get_unique_filename(target_folder, filename)
                    target_path = os.path.join(target_folder, unique_filename)

                    # Record the move operation as a tuple (source, destination)
                    # This will be used for the undo functionality
                    moved_files.append((file_path, target_path))

                    # Show the planned move in preview mode
                    if preview:
                        rename_note = f" (renamed to {unique_filename})" if unique_filename != filename else ""
                        print(f"  {filename} -> {category}/{unique_filename}{rename_note}")
                    else:
                        # Actually move the file if not in preview mode
                        # shutil.move handles the physical file system operation
                        shutil.move(file_path, target_path)
                    
                    stats["categorized"] += 1

                    # Mark file as successfully categorized and exit the category loop
                    moved = True
                    break  # Stop checking other categories once a match is found
                    
                except PermissionError:
                    print(f"\nError: Permission denied when moving '{filename}'")
                    stats["errors"] += 1
                    moved = True  # Mark as moved to prevent falling through to "Others"
                    break
                except Exception as e:
                    print(f"\nError: Could not move '{filename}': {e}")
                    stats["errors"] += 1
                    moved = True
                    break

        # If file doesn't match any category, move it to the "Others" folder
        # This ensures all files are organized, even unknown types
        if not moved:
            try:
                # Create "Others" folder for uncategorized files
                other_folder = os.path.join(folder_path, "Others")
                
                if not preview:
                    os.makedirs(other_folder, exist_ok=True)

                # Get unique filename to handle duplicates
                unique_filename = get_unique_filename(other_folder, filename)
                target_path = os.path.join(other_folder, unique_filename)
                
                # Record the move operation
                moved_files.append((file_path, target_path))

                # Show the planned move in preview mode
                if preview:
                    rename_note = f" (renamed to {unique_filename})" if unique_filename != filename else ""
                    print(f"  {filename} -> Others/{unique_filename}{rename_note}")
                else:
                    # Move the file if not in preview mode
                    shutil.move(file_path, target_path)
                
                stats["others"] += 1
                
            except PermissionError:
                print(f"\nError: Permission denied when moving '{filename}'")
                stats["errors"] += 1
            except Exception as e:
                print(f"\nError: Could not move '{filename}': {e}")
                stats["errors"] += 1

    # Save undo log only if files were actually moved (not in preview mode)
    # This allows users to revert the organization if needed
    if not preview and moved_files:
        save_undo(moved_files)

    # Display summary and completion message
    print("\n" + "="*50)
    if preview:
        print("PREVIEW SUMMARY:")
        print(f"  Files to be categorized: {stats['categorized']}")
        print(f"  Files to move to 'Others': {stats['others']}")
        print(f"  Total files: {stats['categorized'] + stats['others']}")
        print("\nNo files were moved. Run without --preview to apply changes.")
    else:
        print("ORGANIZATION SUMMARY:")
        print(f"  Files categorized: {stats['categorized']}")
        print(f"  Files moved to 'Others': {stats['others']}")
        if stats["errors"] > 0:
            print(f"  Errors encountered: {stats['errors']}")
        print(f"  Total files organized: {stats['categorized'] + stats['others']}")
        print("\nFile organization completed successfully!")
        if moved_files:
            print("Run with --undo to revert these changes.")
    print("="*50)


# =============================
# UNDO FUNCTIONALITY
# =============================

# File to store the history of file movements for undo functionality
# This JSON file contains a list of [source, destination] pairs for each moved file
UNDO_LOG = "undo_log.json"


def save_undo(moves):
    """
    Save the list of file movements to a JSON log file for undo support.
    
    This function creates or overwrites the undo log file with the current organization's
    file movements. Each time files are organized, the previous undo log is replaced,
    meaning only the most recent organization can be undone.
    
    Args:
        moves (list of tuples): List of file movement pairs, where each tuple contains:
                               (source_path, destination_path)
                               Example: [
                                   ("C:/Downloads/photo.jpg", "C:/Downloads/Images/photo.jpg"),
                                   ("C:/Downloads/doc.pdf", "C:/Downloads/PDFs/doc.pdf")
                               ]
    
    Returns:
        None: Prints a confirmation message when the log is saved
    
    Side Effects:
        - Creates or overwrites the undo_log.json file in the current directory
        - The file is formatted with 4-space indentation for readability
    
    Example:
        >>> moves = [("file1.txt", "Documents/file1.txt"), ("pic.jpg", "Images/pic.jpg")]
        >>> save_undo(moves)
        Undo log saved.
    """
    # Open the undo log file in write mode (creates new or overwrites existing)
    with open(UNDO_LOG, "w") as f:
        # Write the moves list as formatted JSON with 4-space indentation
        # indent=4 makes the file human-readable
        json.dump(moves, f, indent=4)
    
    # Confirm that the undo log was successfully saved
    print("Undo log saved.")


def undo_last_operation():
    """
    Reverse the last file organization operation by moving files back to their original locations.
    
    This function reads the undo log file and moves each file from its current organized
    location back to its original location in the root folder. This effectively reverses
    the last organization operation.
    
    The function performs the following steps:
    1. Checks if an undo log exists
    2. Loads the list of file movements from the log
    3. Reverses each movement by swapping source and destination
    4. Moves files back to their original locations
    
    Returns:
        None: Prints status messages about the undo operation
    
    Side Effects:
        - Moves files from organized subfolders back to the root folder
        - Does NOT delete the undo log file (it remains for reference)
        - Displays a progress bar during the reverting process
    
    Notes:
        - Only files that still exist in their organized location will be moved
        - If a file was manually moved or deleted after organization, it will be skipped
        - The undo log is not cleared, so running undo twice may cause errors
    
    Example:
        >>> undo_last_operation()
        Reverting: 100%|████████████| 50/50 [00:01<00:00, 40.00it/s]
        Undo completed.
        
        >>> undo_last_operation()  # If no log exists
        No undo history found.
    """
    # Check if undo log file exists in the current directory
    if not os.path.exists(UNDO_LOG):
        print("Error: No undo history found.")
        print(f"The undo log file '{UNDO_LOG}' does not exist.")
        return  # Exit the function early if no log exists

    try:
        # Load the list of file movements from the JSON log file
        with open(UNDO_LOG, "r") as f:
            moves = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: The undo log file '{UNDO_LOG}' is corrupted or invalid.")
        return
    except Exception as e:
        print(f"Error: Could not read undo log: {e}")
        return
    
    if not moves:
        print("Undo log is empty. Nothing to undo.")
        return
    
    print(f"Found {len(moves)} file movement(s) to revert.\n")
    
    # Track statistics
    reverted = 0
    not_found = 0
    errors = 0
    
    # Reverse each move by swapping source and destination
    # Original format: [(source, dest), (source, dest), ...]
    # Reversed format: [(dest, source), (dest, source), ...]
    # This list comprehension creates tuples with swapped positions: (m[1], m[0])
    for dest, src in tqdm([(m[1], m[0]) for m in moves], desc="Reverting"):
        # Check if the file still exists in its organized location
        # This prevents errors if files were manually moved or deleted
        if os.path.exists(dest):
            try:
                # Move the file back to its original location
                # dest is the current location (in organized folder)
                # src is the original location (root folder)
                shutil.move(dest, src)
                reverted += 1
            except PermissionError:
                print(f"\nError: Permission denied when reverting '{os.path.basename(dest)}'")
                errors += 1
            except Exception as e:
                print(f"\nError: Could not revert '{os.path.basename(dest)}': {e}")
                errors += 1
        else:
            # File doesn't exist in expected location
            not_found += 1

    # Display summary
    print("\n" + "="*50)
    print("UNDO SUMMARY:")
    print(f"  Files reverted: {reverted}")
    if not_found > 0:
        print(f"  Files not found (skipped): {not_found}")
    if errors > 0:
        print(f"  Errors encountered: {errors}")
    
    if reverted > 0:
        print("\nUndo completed successfully!")
    elif not_found == len(moves):
        print("\nWarning: No files were found to revert.")
        print("Files may have been manually moved or deleted.")
    else:
        print("\nUndo completed with issues.")
    print("="*50)


# =============================
# COMMAND-LINE INTERFACE
# =============================

# This block only runs when the script is executed directly (not imported as a module)
if __name__ == "__main__":
    # Create an argument parser for handling command-line arguments
    # The description appears in the help message when users run: python File_organizer.py --help
    parser = argparse.ArgumentParser(
        description="Desktop File Organizer - Automatically organize files into categorized folders",
        epilog="Example: python File_organizer.py ~/Downloads --preview"
    )

    # Define positional argument: the folder path to organize
    # This is required and must be provided by the user (unless using --undo)
    # Example: python File_organizer.py ~/Downloads
    parser.add_argument(
        "path",
        nargs="?",  # Make path optional when using --undo
        help="Path to the folder you want to organize (absolute or relative path)"
    )
    
    # Define optional flag: --preview
    # action="store_true" means this is a boolean flag (no value needed)
    # If --preview is present, args.preview will be True; otherwise False
    # Example: python File_organizer.py ~/Downloads --preview
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: Show what will happen without actually moving any files"
    )
    
    # Define optional flag: --undo
    # This flag allows users to revert the last organization operation
    # Example: python File_organizer.py ~/Downloads --undo
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the last organization operation and restore files to original locations"
    )

    # Parse the command-line arguments provided by the user
    # This converts the raw command-line input into a structured args object
    # Example: If user runs "python File_organizer.py ~/Downloads --preview"
    #          Then: args.path = "~/Downloads", args.preview = True, args.undo = False
    args = parser.parse_args()

    # Execute the appropriate action based on the provided arguments
    # The --undo flag takes precedence over normal organization
    if args.undo:
        # User wants to undo the last organization
        # The path argument is ignored in undo mode
        undo_last_operation()
    else:
        # Validate that path was provided for organize operation
        if not args.path:
            parser.error("the following arguments are required: path (unless using --undo)")
        
        # User wants to organize files (either preview or actual)
        # Pass the folder path and preview flag to the organize_files function
        organize_files(args.path, preview=args.preview)
