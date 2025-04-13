import os
import cv2
from datetime import datetime
from PIL import Image, ImageTk
from tkinter import ttk, NSEW, W, E
from tkinter import Frame,StringVar, Canvas, messagebox
from tkinter import LEFT
from utils.media_paths import get_reference_image_path
from utils.resource_manager import save_parking_positions
from ui.parking_allocation_tab import ParkingAllocationTab

# Import statements...

class SetupTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app

        # Setup UI components
        self.setup_ui()

        # Initialize drawing variables
        self.drawing = False
        self.start_x, self.start_y = -1, -1
        self.current_rect = None

    def setup_ui(self):
        """Set up the setup tab UI with responsive design"""
        # Configure grid layout
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_rowconfigure(0, weight=0)  # Control bar (fixed height)
        self.parent.grid_rowconfigure(1, weight=1)  # Canvas (expandable)

        # Frame for setup controls (top)
        self.setup_control_frame = ttk.Frame(self.parent, padding=5)
        self.setup_control_frame.grid(row=0, column=0, sticky="ew")

        # Configure columns in control frame for better spacing
        for i in range(10):  # Divide into 10 columns for better control
            self.setup_control_frame.columnconfigure(i, weight=1)

        # Title and instructions
        ttk.Label(self.setup_control_frame, text="Parking Space Setup",
                  font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky=W, padx=5)

        ttk.Label(self.setup_control_frame, text="Left-click and drag to draw spaces. Right-click to delete spaces.",
                  font=("Arial", 10)).grid(row=0, column=2, columnspan=3, sticky=W, padx=5)

        # Calibration controls
        calibration_frame = ttk.LabelFrame(self.setup_control_frame, text="Calibration")
        calibration_frame.grid(row=0, column=5, columnspan=2, padx=5, pady=2)

        # Arrange buttons in a grid inside the frame
        ttk.Button(calibration_frame, text="↑", width=3,
                   command=lambda: self.shift_all_spaces(0, -5)).grid(row=0, column=1)
        ttk.Button(calibration_frame, text="←", width=3,
                   command=lambda: self.shift_all_spaces(-5, 0)).grid(row=1, column=0)
        ttk.Button(calibration_frame, text="→", width=3,
                   command=lambda: self.shift_all_spaces(5, 0)).grid(row=1, column=2)
        ttk.Button(calibration_frame, text="↓", width=3,
                   command=lambda: self.shift_all_spaces(0, 5)).grid(row=2, column=1)

        # Reference image selection
        ttk.Label(self.setup_control_frame, text="Reference Image:").grid(row=0, column=7, sticky=E, padx=5)
        self.ref_image_var = StringVar(value=self.app.current_reference_image)
        self.ref_image_menu = ttk.Combobox(self.setup_control_frame, textvariable=self.ref_image_var,
                                           width=15, values=list(self.app.video_reference_map.values()))
        self.ref_image_menu.grid(row=0, column=8, padx=5)
        self.ref_image_menu.bind("<<ComboboxSelected>>", lambda e: self.load_reference_image(self.ref_image_var.get()))

        # Action buttons (right side)
        action_buttons_frame = ttk.Frame(self.setup_control_frame)
        action_buttons_frame.grid(row=0, column=9, sticky=E)

        ttk.Button(action_buttons_frame, text="Save Spaces",
                   command=self.save_parking_spaces).pack(side=LEFT, padx=2)
        ttk.Button(action_buttons_frame, text="Clear All",
                   command=self.clear_all_spaces).pack(side=LEFT, padx=2)
        ttk.Button(action_buttons_frame, text="Reset Calibration",
                   command=self.reset_reference_calibration).pack(side=LEFT, padx=2)
        ttk.Button(action_buttons_frame, text="Associate Video",
                   command=self.associate_video_with_reference).pack(side=LEFT, padx=2)

        # Frame for the setup canvas (expandable) with scrollbars
        self.setup_canvas_frame = Frame(self.parent, bg='black')
        self.setup_canvas_frame.grid(row=1, column=0, sticky=NSEW, padx=5, pady=5)
        self.setup_canvas_frame.grid_rowconfigure(0, weight=1)
        self.setup_canvas_frame.grid_columnconfigure(0, weight=1)

        # Add horizontal and vertical scrollbars
        self.h_scrollbar = ttk.Scrollbar(self.setup_canvas_frame, orient="horizontal")
        self.v_scrollbar = ttk.Scrollbar(self.setup_canvas_frame, orient="vertical")

        self.setup_canvas = Canvas(self.setup_canvas_frame, bg='black',
                                   xscrollcommand=self.h_scrollbar.set,
                                   yscrollcommand=self.v_scrollbar.set)

        self.h_scrollbar.config(command=self.setup_canvas.xview)
        self.v_scrollbar.config(command=self.setup_canvas.yview)

        # Grid layout for canvas and scrollbars
        self.setup_canvas.grid(row=0, column=0, sticky=NSEW)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        # Setup mouse events
        self.setup_canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.setup_canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.setup_canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.setup_canvas.bind("<ButtonPress-3>", self.on_right_click)

        # Add mouse wheel scrolling
        self.setup_canvas.bind("<MouseWheel>", self.on_mouse_wheel)  # Windows
        self.setup_canvas.bind("<Button-4>", self.on_mouse_wheel)    # Linux scroll up
        self.setup_canvas.bind("<Button-5>", self.on_mouse_wheel)    # Linux scroll down

        # Load reference image
        self.load_reference_image()

        # Create notebook widget
        self.notebook = ttk.Notebook(self.setup_canvas_frame)
        self.notebook.grid(row=2, column=0, sticky=NSEW, padx=5, pady=5)

        # allocation_tab = ttk.Frame(self.notebook)
        # self.notebook.add(allocation_tab, text="Parking Allocation")
        # self.parking_allocation_tab = ParkingAllocationTab(allocation_tab, self)

    def on_mouse_wheel(self, event):
        """Handle mouse wheel scrolling"""
        # Determine scroll direction and amount
        if event.num == 4 or event.delta > 0:
            self.setup_canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.setup_canvas.yview_scroll(1, "units")

    def load_reference_image(self, image_name=None):
        """Load and display the reference image for parking space setup"""
        try:
            if image_name is None:
                image_name = self.app.current_reference_image
            else:
                self.app.current_reference_image = image_name

            # Use get_reference_image_path to find the image
            self.ref_image_path = get_reference_image_path(image_name)

            if os.path.exists(self.ref_image_path):
                self.ref_img = cv2.imread(self.ref_image_path)
                if self.ref_img is None:
                    raise Exception(f"Could not load image file: {self.ref_image_path}")

                # Get original dimensions
                orig_height, orig_width = self.ref_img.shape[:2]

                # Store original dimensions if not already defined
                if image_name not in self.app.reference_dimensions:
                    self.app.reference_dimensions[image_name] = (orig_width, orig_height)

                # Resize to match the video dimensions if you know them
                if hasattr(self.app, 'image_width') and hasattr(self.app, 'image_height'):
                    self.ref_img = cv2.resize(self.ref_img, (self.app.image_width, self.app.image_height))

                self.ref_img = cv2.cvtColor(self.ref_img, cv2.COLOR_BGR2RGB)
                self.ref_img_pil = Image.fromarray(self.ref_img)
                self.ref_img_tk = ImageTk.PhotoImage(image=self.ref_img_pil)

                # Configure canvas for scrolling
                self.setup_canvas.config(width=self.app.image_width, height=self.app.image_height,
                                        scrollregion=(0, 0, self.app.image_width, self.app.image_height))
                self.image_id = self.setup_canvas.create_image(0, 0, anchor="nw", image=self.ref_img_tk)

                # Draw any existing parking spaces
                self.draw_parking_spaces()
            else:
                messagebox.showwarning("Warning",
                                       f"Reference image '{image_name}' not found at path '{self.ref_image_path}'")
                self.app.log_event(f"Warning: Reference image not found: {self.ref_image_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reference image: {str(e)}")
            self.app.log_event(f"Error loading reference image: {str(e)}")

    def draw_parking_spaces(self):
        """Draw the defined parking spaces on the setup canvas"""
        try:
            # First clear any existing rectangles
            self.setup_canvas.delete("parking_space")

            # Draw each parking space - limit processing to visible spaces
            for i, (x, y, w, h) in enumerate(self.app.posList):
                self.setup_canvas.create_rectangle(
                    x, y, x + w, y + h,
                    outline="magenta", width=2,
                    tags=("parking_space", f"space_{i}")
                )

                # Add space number (only if we have less than 50 spaces to avoid performance issues)
                if len(self.app.posList) < 50:
                    self.setup_canvas.create_text(
                        x + w / 2, y + h / 2,
                        text=str(i + 1),
                        fill="white",
                        tags=("parking_space", f"space_text_{i}")
                    )
        except Exception as e:
            self.app.log_event(f"Error drawing parking spaces: {str(e)}")

    def on_mouse_down(self, event):
        """Handle mouse down event for drawing parking spaces"""
        self.drawing = True
        # Adjust coordinates for canvas scroll position
        self.start_x = self.setup_canvas.canvasx(event.x)
        self.start_y = self.setup_canvas.canvasy(event.y)

        # Create a new rectangle
        self.current_rect = self.setup_canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="green", width=2, tags="current_rect"
        )

    def on_mouse_move(self, event):
        """Handle mouse move event while drawing parking spaces"""
        if self.drawing:
            # Adjust coordinates for canvas scroll position
            current_x = self.setup_canvas.canvasx(event.x)
            current_y = self.setup_canvas.canvasy(event.y)

            # Update rectangle size
            self.setup_canvas.coords(self.current_rect,
                                     self.start_x, self.start_y, current_x, current_y)

    def on_mouse_up(self, event):
        """Handle mouse up event to finish drawing parking spaces"""
        if not self.drawing:
            return

        self.drawing = False
        end_x = self.setup_canvas.canvasx(event.x)
        end_y = self.setup_canvas.canvasy(event.y)

        # Calculate width and height
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)

        # Ensure we have the top-left coordinates for storage
        x_pos = min(self.start_x, end_x)
        y_pos = min(self.start_y, end_y)

        # Only add if rectangle has meaningful size
        if width > 5 and height > 5:
            try:
                # Add to posList first (display dimensions)
                self.app.posList.append((x_pos, y_pos, width, height))

                # Get reference dimensions for original_posList
                if hasattr(self.app,
                           'reference_dimensions') and self.app.current_reference_image in self.app.reference_dimensions:
                    ref_width, ref_height = self.app.reference_dimensions[self.app.current_reference_image]

                    # Calculate inverse scale factors (display → reference)
                    width_scale = ref_width / self.app.image_width
                    height_scale = ref_height / self.app.image_height

                    # Scale to reference dimensions
                    ref_x = int(x_pos * width_scale)
                    ref_y = int(y_pos * height_scale)
                    ref_w = int(width * width_scale)
                    ref_h = int(height * height_scale)

                    # Add to original_posList (reference dimensions)
                    if not hasattr(self.app, 'original_posList'):
                        self.app.original_posList = []
                    self.app.original_posList.append((ref_x, ref_y, ref_w, ref_h))
                else:
                    # If no reference dimensions, just copy posList
                    if not hasattr(self.app, 'original_posList'):
                        self.app.original_posList = []
                    self.app.original_posList.append((x_pos, y_pos, width, height))

                # Update total spaces
                self.app.total_spaces = len(self.app.posList)
                self.app.occupied_spaces = self.app.total_spaces
                self.app.update_status_info()

                # Draw the newly added parking space immediately
                last_idx = len(self.app.posList) - 1
                x, y, w, h = self.app.posList[last_idx]
                self.setup_canvas.create_rectangle(
                    x, y, x + w, y + h,
                    outline="magenta", width=2,
                    tags=("parking_space", f"space_{last_idx}")
                )

                # Schedule the allocation update for later to prevent UI freeze
                self.parent.after(100, self.update_allocation_data)

            except Exception as e:
                self.app.log_event(f"Error adding parking space: {str(e)}")

        # Remove the temporary rectangle
        self.setup_canvas.delete("current_rect")

    def on_right_click(self, event):
        """Handle right-click to delete a parking space"""
        # Adjust coordinates for canvas scroll position
        x = self.setup_canvas.canvasx(event.x)
        y = self.setup_canvas.canvasy(event.y)

        # Check if click is inside any parking space
        for i, (x1, y1, w, h) in enumerate(self.app.posList):
            if x1 <= x <= x1 + w and y1 <= y <= y1 + h:
                # Remove from the list
                self.app.posList.pop(i)

                # Update total spaces
                self.app.total_spaces = len(self.app.posList)
                self.app.occupied_spaces = self.app.total_spaces
                self.app.update_status_info()

                # Redraw all spaces
                self.draw_parking_spaces()
                break

    def shift_all_spaces(self, dx, dy):
        """Shift all parking spaces by dx, dy"""
        for i in range(len(self.app.posList)):
            x, y, w, h = self.app.posList[i]
            self.app.posList[i] = (x + dx, y + dy, w, h)

        # Redraw spaces
        self.draw_parking_spaces()
        self.app.log_event(f"Shifted all spaces by ({dx}, {dy})")

    def add_position(self, event):
        """Add a parking position at the clicked location"""
        x, y = event.x, event.y

        # Scale coordinates to match stored image dimensions
        x_scale = self.image_width / self.canvas_width
        y_scale = self.image_height / self.canvas_height

        scaled_x = int(x * x_scale)
        scaled_y = int(y * y_scale)

        # Use default size or scale from settings
        w = 60  # Default width
        h = 90  # Default height

        # Add to positions list
        self.app.posList.append((scaled_x, scaled_y, w, h))

        # Update the parking manager and allocation systems
        if hasattr(self.app, 'parking_manager'):
            # Generate section based on position
            section = "A" if scaled_x < self.image_width / 2 else "B"
            section += "1" if scaled_y < self.image_height / 2 else "2"

            space_id = f"S{len(self.app.posList)}-{section}"

            # Create with occupied=True by default
            self.app.parking_manager.parking_data[space_id] = {
                'position': (scaled_x, scaled_y, w, h),
                'occupied': True,  # Set to TRUE by default
                'vehicle_id': None,
                'last_state_change': datetime.now(),
                'distance_to_entrance': scaled_x + scaled_y,
                'section': section
            }

        # Update counters
        self.app.total_spaces = len(self.app.posList)
        self.app.free_spaces = 0  # Reset free spaces counter
        self.app.occupied_spaces = self.app.total_spaces

        # Update the allocation data
        self.update_allocation_data()

        # Draw the rectangle
        self.draw_positions()

        # Update status info
        self.app.update_status_info()

    def save_parking_spaces(self):
        """Save the defined parking spaces to a file"""
        try:
            # If original_posList exists, use it (it's already in reference dimensions)
            if hasattr(self.app, 'original_posList') and self.app.original_posList:
                self.app.log_event(f"Saving {len(self.app.original_posList)} spaces from original_posList")
                save_positions = self.app.original_posList
            # Otherwise scale back to reference dimensions before saving
            elif self.app.current_reference_image in self.app.reference_dimensions:
                ref_width, ref_height = self.app.reference_dimensions[self.app.current_reference_image]

                # Calculate scale factors (inverse of what we use for display)
                width_scale = ref_width / self.app.image_width
                height_scale = ref_height / self.app.image_height

                self.app.log_event(
                    f"Saving positions: Scaling from display {self.app.image_width}x{self.app.image_height} "
                    f"to reference {ref_width}x{ref_height}")

                # Scale all positions back to reference dimensions
                reference_positions = []
                for x, y, w, h in self.app.posList:
                    ref_x = int(x * width_scale)
                    ref_y = int(y * height_scale)
                    ref_w = int(w * width_scale)
                    ref_h = int(h * height_scale)
                    reference_positions.append((ref_x, ref_y, ref_w, ref_h))

                # Store the reference positions as the original positions
                self.app.original_posList = reference_positions.copy()
                save_positions = reference_positions
            else:
                save_positions = self.app.posList
                self.app.original_posList = self.app.posList.copy()

            # Save using the utility function
            success = save_parking_positions(save_positions, self.app.config_dir, self.app.current_reference_image)

            if success:
                self.app.log_event(
                    f"Saved {len(self.app.posList)} parking spaces for {self.app.current_reference_image}")
                messagebox.showinfo("Success",
                                    f"Saved {len(self.app.posList)} parking spaces for {self.app.current_reference_image}.")

                # Update allocation data after saving
                self.update_allocation_data()
            else:
                messagebox.showerror("Error", "Failed to save parking spaces.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save parking spaces: {str(e)}")
            self.app.log_event(f"Error saving parking spaces: {str(e)}")

    def reset_reference_calibration(self):
        """Reset the calibration for the current reference image"""
        if messagebox.askyesno("Reset Calibration",
                               f"Are you sure you want to reset calibration for {self.app.current_reference_image}?"):
            # Clear positions for current reference
            self.app.posList = []

            # Delete stored file if it exists
            import os
            pos_file = os.path.join(self.app.config_dir,
                                    f'CarParkPos_{os.path.splitext(self.app.current_reference_image)[0]}')
            if os.path.exists(pos_file):
                try:
                    os.remove(pos_file)
                    self.app.log_event(f"Deleted calibration file for {self.app.current_reference_image}")
                except Exception as e:
                    self.app.log_event(f"Error deleting calibration file: {str(e)}")

            # Clear canvas
            self.draw_parking_spaces()

            # Update UI
            self.app.total_spaces = 0
            self.app.free_spaces = 0
            self.app.occupied_spaces = 0
            self.app.update_status_info()

            self.app.log_event(f"Reset calibration for {self.app.current_reference_image}")

    def clear_all_spaces(self):
        """Clear all defined parking spaces"""
        if messagebox.askyesno("Confirm", "Are you sure you want to delete all parking spaces?"):
            self.app.posList = []
            self.draw_parking_spaces()
            self.app.total_spaces = 0
            self.app.free_spaces = 0
            self.app.occupied_spaces = 0
            self.app.update_status_info()
            self.app.log_event("Cleared all parking spaces")

    def browse_reference_image(self):
        """Browse for a new reference image and add it to the system"""
        from tkinter import filedialog

        # Open file dialog to select image
        file_path = filedialog.askopenfilename(
            title="Select Reference Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp")]
        )

        if file_path:
            # Get just the filename
            file_name = os.path.basename(file_path)

            # Check if the file is already in the working directory
            if not os.path.exists(file_name):
                # Copy the file to the working directory
                import shutil
                try:
                    shutil.copy(file_path, file_name)
                    self.app.log_event(f"Copied reference image {file_name} to working directory")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to copy reference image: {str(e)}")
                    return

            # Get image dimensions
            try:
                img = cv2.imread(file_name)
                height, width = img.shape[:2]

                # Add to reference dimensions
                self.app.reference_dimensions[file_name] = (width, height)

                # Update dropdown menu
                menu = self.ref_image_menu["menu"]
                menu.delete(0, "end")
                for ref_img in list(self.app.video_reference_map.values()) + [file_name]:
                    menu.add_command(label=ref_img,
                                     command=lambda value=ref_img: self.ref_image_var.set(
                                         value) or self.load_reference_image(value))

                # Select the new image
                self.ref_image_var.set(file_name)
                self.load_reference_image(file_name)

                self.app.log_event(f"Added reference image {file_name} ({width}x{height})")
                messagebox.showinfo("Success", f"Added reference image: {file_name}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to process reference image: {str(e)}")
                self.app.log_event(f"Error processing reference image: {str(e)}")

    def associate_video_with_reference(self):
        """Associate a video source with a reference image"""
        from utils.dialogs import AssociateDialog

        # Check if video sources are available
        if not hasattr(self.app, 'video_sources') or not self.app.video_sources:
            messagebox.showerror("Error", "No video sources available")
            return

        # Show dialog
        dialog = AssociateDialog(self.parent, self.app)
        result = dialog.show()

        # If successful, update UI and show confirmation
        if result:
            video, ref_img = result
            # Update UI if needed
            if hasattr(self.app, 'reference_tab'):
                self.app.reference_tab.populate_reference_tree()

            messagebox.showinfo("Success", f"Associated {video} with {ref_img}")

    def update_allocation_data(self):
        """Update parking allocation data with newly drawn spaces - optimized version"""
        try:
            # Make sure app has parking_manager
            if not hasattr(self.app, 'parking_manager'):
                from models.parking_manager import ParkingManager
                self.app.parking_manager = ParkingManager(config_dir=self.app.config_dir, log_dir=self.app.log_dir)

            # Make sure parking_data exists
            if not hasattr(self.app.parking_manager, 'parking_data'):
                self.app.parking_manager.parking_data = {}

            # Clear existing data to rebuild from scratch
            self.app.parking_manager.parking_data.clear()  # Use clear() instead of reassigning

            # Import datetime class
            from datetime import datetime

            # For each parking space in posList, create an entry in parking_data
            for i, (x, y, w, h) in enumerate(self.app.posList):
                # Generate section based on position
                section = "A" if x < self.app.image_width / 2 else "B"
                section += "1" if y < self.app.image_height / 2 else "2"

                # Create space ID
                space_id = f"S{i + 1}-{section}"

                # Add to parking_data
                self.app.parking_manager.parking_data[space_id] = {
                    'position': (x, y, w, h),
                    'occupied': False,  # Default to unoccupied
                    'vehicle_id': None,
                    'last_state_change': datetime.now(),
                    'distance_to_entrance': x + y,  # Simple distance estimation
                    'section': section
                }

            # Don't update the UI elements directly from this function
            # Instead, schedule the update for later
            self.app.log_event(f"Updated allocation data with {len(self.app.posList)} parking spaces")
        except Exception as e:
            self.app.log_event(f"Error updating allocation data: {str(e)}")