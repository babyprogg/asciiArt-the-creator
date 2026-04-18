import cv2
from PIL import Image, ImageEnhance
import numpy as np
import tkinter as tk
from tkinter import filedialog, ttk, colorchooser, scrolledtext
from tkinter.messagebox import showinfo
import os

ASCII_SETS = {
    "Стандартный": "@%#*+=-:. "[::-1],
    "Плотный": "@#S%?*+;:-,. "[::-1],
    "Детальный": "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
}

class ASCIIPlayerWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ASCII ML Player — Улучшенная версия")
        self.root.geometry("1280x880")
        self.root.configure(bg="#1e1e1e")

        # Настройки
        self.ascii_width = tk.IntVar(value=140)
        self.brightness = tk.DoubleVar(value=1.0)
        self.contrast = tk.DoubleVar(value=1.0)
        self.current_set = tk.StringVar(value="Стандартный")
        self.use_edges = tk.BooleanVar(value=False)
        self.use_color = tk.BooleanVar(value=True)

        self.is_running = False
        self.current_job = None
        self.cap = None
        self.gif = None
        self.current_ascii = ""
        self.current_filename = ""
        self.last_pil_image = None   # для повторного применения настроек к фото

        self.setup_ui()

    def setup_ui(self):
        # Главный фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # === Задвижная панель настроек ===
        self.settings_frame = ttk.LabelFrame(main_frame, text="Настройки ASCII (нажми чтобы свернуть/развернуть)", padding=10)
        self.settings_frame.pack(fill="x", pady=(0, 10))

        # Кнопка сворачивания
        self.toggle_btn = ttk.Button(self.settings_frame, text="▼ Скрыть настройки", command=self.toggle_settings)
        self.toggle_btn.pack(fill="x", pady=(0, 8))

        self.inner_settings = ttk.Frame(self.settings_frame)
        self.inner_settings.pack(fill="x")

        # Ширина
        ttk.Label(self.inner_settings, text="Ширина ASCII:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Scale(self.inner_settings, from_=80, to=220, variable=self.ascii_width, 
                 command=self.live_update).grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Label(self.inner_settings, textvariable=self.ascii_width).grid(row=0, column=2)

        # Набор символов
        ttk.Label(self.inner_settings, text="Набор символов:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(self.inner_settings, textvariable=self.current_set, 
                    values=list(ASCII_SETS.keys()), state="readonly").grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        # Яркость
        ttk.Label(self.inner_settings, text="Яркость:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Scale(self.inner_settings, from_=0.5, to=2.0, variable=self.brightness, 
                 command=self.live_update).grid(row=2, column=1, sticky="ew", padx=10)

        # Контраст
        ttk.Label(self.inner_settings, text="Контраст:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Scale(self.inner_settings, from_=0.5, to=2.0, variable=self.contrast, 
                 command=self.live_update).grid(row=3, column=1, sticky="ew", padx=10)

        ttk.Checkbutton(self.inner_settings, text="Цветной ASCII", variable=self.use_color).grid(row=4, column=0, columnspan=3, sticky="w", pady=6)
        ttk.Checkbutton(self.inner_settings, text="Улучшить края (Canny)", variable=self.use_edges).grid(row=5, column=0, columnspan=3, sticky="w")

        # Кнопка "Применить к текущему фото"
        ttk.Button(self.inner_settings, text="Применить настройки к фото", 
                  command=self.apply_to_current_image).grid(row=6, column=0, columnspan=3, pady=8)

        # Панель кнопок
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=5)

        ttk.Button(btn_frame, text="Открыть файл", command=self.open_file).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Запустить камеру", command=self.start_webcam).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Сделать фото", command=self.capture_photo).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Остановить", command=self.stop).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Сохранить ASCII", command=self.save_ascii).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Цвета окна", command=self.choose_colors).pack(side="left", padx=5)

        # Область ASCII
        self.text_area = scrolledtext.ScrolledText(
            main_frame, font=("Consolas", 10, "bold"), bg="#0a0a0a", fg="#00ff41",
            wrap="none", state="disabled"
        )
        self.text_area.pack(fill="both", expand=True, pady=10)

        self.status_label = ttk.Label(main_frame, text="Готов к работе")
        self.status_label.pack()

        self.current_set.trace("w", self.live_update)

    def toggle_settings(self):
        if self.inner_settings.winfo_ismapped():
            self.inner_settings.pack_forget()
            self.toggle_btn.config(text="▶ Развернуть настройки")
        else:
            self.inner_settings.pack(fill="x")
            self.toggle_btn.config(text="▼ Скрыть настройки")

    def live_update(self, *args):
        if self.is_running:
            self.status_label.config(text="Настройки обновлены (камера обновляется автоматически)")

    def image_to_ascii(self, pil_image):
        # Применяем яркость и контраст
        if self.brightness.get() != 1.0:
            pil_image = ImageEnhance.Brightness(pil_image).enhance(self.brightness.get())
        if self.contrast.get() != 1.0:
            pil_image = ImageEnhance.Contrast(pil_image).enhance(self.contrast.get())

        width = self.ascii_width.get()
        aspect = pil_image.height / pil_image.width
        new_h = int(aspect * width * 0.55)

        resized = pil_image.resize((width, new_h))
        gray = resized.convert('L')
        arr = np.array(gray)

        if self.use_edges.get():
            arr = cv2.Canny(arr, 40, 140)

        chars = ASCII_SETS[self.current_set.get()]
        divisor = 256 / len(chars)
        ascii_str = ''.join(chars[min(int(p / divisor), len(chars)-1)] for p in arr.flatten())

        lines = [ascii_str[i:i+width] for i in range(0, len(ascii_str), width)]
        return '\n'.join(lines), resized

    def update_display(self, ascii_text, pil_image=None, filename=""):
        self.current_ascii = ascii_text
        self.last_pil_image = pil_image
        self.current_filename = filename

        self.text_area.config(state="normal")
        self.text_area.delete(1.0, tk.END)

        if self.use_color.get() and pil_image:
            r, g, b = pil_image.resize((1, 1)).convert('RGB').getpixel((0, 0))
            color = f'#{r:02x}{g:02x}{b:02x}'
            self.text_area.insert(tk.END, ascii_text, "color")
            self.text_area.tag_configure("color", foreground=color)
        else:
            self.text_area.insert(tk.END, ascii_text)

        if filename:
            self.text_area.insert(tk.END, f"\n\nФайл: {filename}")
        self.text_area.config(state="disabled")

    def apply_to_current_image(self):
        """Применяет текущие настройки к последнему загруженному фото"""
        if self.last_pil_image is None:
            showinfo("Внимание", "Сначала открой фото или сделай снимок с камеры")
            return

        ascii_art, processed_img = self.image_to_ascii(self.last_pil_image)
        self.update_display(ascii_art, processed_img, self.current_filename)
        self.status_label.config(text="Настройки применены к фото")

    # ==================== Открытие файлов ====================
    def open_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Поддерживаемые файлы", "*.jpg *.jpeg *.png *.gif *.mp4 *.avi *.mov *.mkv *.webm")]
        )
        if not file_path:
            return
        self.stop()

        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path)

        try:
            if ext == '.gif':
                self.play_gif(file_path, filename)
            elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                self.play_video(file_path, filename)
            else:
                # Обычное фото
                img = Image.open(file_path).convert('RGB')
                ascii_art, processed = self.image_to_ascii(img)
                self.update_display(ascii_art, processed, filename)
                self.status_label.config(text=f"Фото загружено: {filename}")
        except Exception as e:
            showinfo("Ошибка", f"Не удалось открыть файл:\n{e}")

    def play_gif(self, file_path, filename):
        try:
            self.gif = Image.open(file_path)
            self.is_running = True
            self.status_label.config(text=f"GIF запущен: {filename}")
            self._animate_gif(0, filename)
        except Exception as e:
            showinfo("Ошибка GIF", str(e))

    def _animate_gif(self, frame_count, filename):
        if not self.is_running or not self.gif:
            return
        try:
            self.gif.seek(frame_count)
            frame = self.gif.copy().convert('RGB')
            ascii_art, processed = self.image_to_ascii(frame)
            self.update_display(ascii_art, processed, filename)

            self.current_job = self.root.after(
                int(1000 / 18),   # примерно 18 fps для GIF
                lambda: self._animate_gif(frame_count + 1, filename)
            )
        except EOFError:
            self.current_job = self.root.after(50, lambda: self._animate_gif(0, filename))
        except:
            self.stop()

    # Камера и другие методы (start_webcam, capture_photo, stop и т.д.) остались как раньше

    def start_webcam(self):
        self.stop()
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            showinfo("Ошибка", "Не удалось открыть камеру")
            return
        self.is_running = True
        self.status_label.config(text="Камера запущена — Live ASCII")
        self._webcam_loop()

    def _webcam_loop(self):
        if not self.is_running or not self.cap:
            return
        ret, frame = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            ascii_art, processed = self.image_to_ascii(pil)
            self.update_display(ascii_art, processed, "Live Webcam")
        self.current_job = self.root.after(50, self._webcam_loop)

    def capture_photo(self):
        if not self.cap or not self.is_running:
            showinfo("Ошибка", "Сначала запусти камеру")
            return
        ret, frame = self.cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            ascii_art, processed = self.image_to_ascii(pil)
            self.update_display(ascii_art, processed, "Captured Photo")
            cv2.imwrite("ascii_capture.jpg", frame)

    def stop(self):
        self.is_running = False
        if self.current_job:
            self.root.after_cancel(self.current_job)
            self.current_job = None
        if self.cap:
            self.cap.release()
            self.cap = None
        self.status_label.config(text="Остановлено")

    def choose_colors(self):
        color = colorchooser.askcolor(title="Цвет фона", initialcolor="#0a0a0a")
        if color[1]:
            self.text_area.config(bg=color[1])

    def save_ascii(self):
        if not self.current_ascii:
            showinfo("Пусто", "Нет ASCII для сохранения")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="ascii_art.txt")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.current_ascii)
            showinfo("Сохранено!", f"Файл сохранён:\n{path}")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.mainloop()


if __name__ == "__main__":
    app = ASCIIPlayerWindow()
    app.run()