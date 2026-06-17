from __future__ import annotations

from pathlib import Path
from time import perf_counter
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .generation import LocalStudyGenerator, OpenAIStudyGenerator
from .parser import ParseError, parse_file, parse_text, parse_url
from .sessions import PracticeSession, TimedQuizSession


THEMES = {
    "Anime": {
        "bg": "#fff8fb",
        "panel": "#ffffff",
        "text": "#202233",
        "muted": "#5f6478",
        "accent": "#ff5fa2",
        "accent2": "#42c6ff",
        "accent3": "#ffd84d",
        "button_text": "#ffffff",
    },
    "Floral": {
        "bg": "#f7fbf4",
        "panel": "#ffffff",
        "text": "#243126",
        "muted": "#667060",
        "accent": "#4d9b6c",
        "accent2": "#e7789a",
        "accent3": "#f3d26b",
        "button_text": "#ffffff",
    },
    "Game-style": {
        "bg": "#111820",
        "panel": "#1d2833",
        "text": "#f4f7fb",
        "muted": "#aab7c4",
        "accent": "#00d084",
        "accent2": "#ffb000",
        "accent3": "#49a6ff",
        "button_text": "#071017",
    },
}


class ExamBuddyApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Exam Buddy")
        self.geometry("1120x740")
        self.minsize(980, 660)

        self.theme_name = tk.StringVar(value="Anime")
        self.card_count = tk.IntVar(value=8)
        self.quiz_count = tk.IntVar(value=12)
        self.use_ai = tk.BooleanVar(value=False)
        self.url_value = tk.StringVar()
        self.status_value = tk.StringVar(value="Upload a source, paste text, or parse a web link to begin.")
        self.feedback_value = tk.StringVar()
        self.timer_value = tk.StringVar()

        self.parsed_content = None
        self.study_set = None
        self.study_signature = None
        self.flashcard_index = 0
        self.practice_session: PracticeSession | None = None
        self.quiz_session: TimedQuizSession | None = None
        self.quiz_started_at = 0.0
        self.timer_after_id: str | None = None
        self.answer_var = tk.StringVar()
        self.mcq_var = tk.StringVar()

        self._build_layout()
        self._apply_theme()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=0, minsize=340)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self.header = tk.Frame(self, padx=18, pady=14)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header.columnconfigure(1, weight=1)

        self.title_label = tk.Label(self.header, text="Exam Buddy", font=("Segoe UI", 23, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        toolbar = tk.Frame(self.header)
        toolbar.grid(row=0, column=1, sticky="e")
        self._add_labeled_option(toolbar, "Theme", self.theme_name, list(THEMES), 0)
        self.theme_name.trace_add("write", lambda *_: self._apply_theme())

        tk.Label(toolbar, text="Cards").grid(row=0, column=2, padx=(18, 4), sticky="e")
        tk.Spinbox(toolbar, from_=5, to=30, textvariable=self.card_count, width=4).grid(row=0, column=3)
        tk.Label(toolbar, text="Quiz").grid(row=0, column=4, padx=(18, 4), sticky="e")
        tk.Spinbox(toolbar, from_=10, to=15, textvariable=self.quiz_count, width=4).grid(row=0, column=5)
        tk.Checkbutton(toolbar, text="Use AI", variable=self.use_ai).grid(row=0, column=6, padx=(18, 0))

        self.source_panel = tk.Frame(self, padx=16, pady=16)
        self.source_panel.grid(row=1, column=0, sticky="nsew", padx=(18, 9), pady=(0, 18))
        self.source_panel.rowconfigure(9, weight=1)

        tk.Label(self.source_panel, text="Source", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.upload_button = tk.Button(self.source_panel, text="Upload PDF / PPTX", command=self._choose_file)
        self.upload_button.grid(row=1, column=0, sticky="ew", pady=(12, 8))

        tk.Label(self.source_panel, text="Web link").grid(row=2, column=0, sticky="w")
        tk.Entry(self.source_panel, textvariable=self.url_value).grid(row=3, column=0, sticky="ew", pady=(4, 6))
        self.link_button = tk.Button(self.source_panel, text="Parse Link", command=self._parse_link)
        self.link_button.grid(row=4, column=0, sticky="ew", pady=(0, 12))

        tk.Label(self.source_panel, text="Or paste text").grid(row=5, column=0, sticky="w")
        self.paste_text = tk.Text(self.source_panel, height=8, wrap="word")
        self.paste_text.grid(row=6, column=0, sticky="ew", pady=(4, 6))
        self.text_button = tk.Button(self.source_panel, text="Parse Pasted Text", command=self._parse_pasted_text)
        self.text_button.grid(row=7, column=0, sticky="ew", pady=(0, 14))

        tk.Label(self.source_panel, text="Key concepts", font=("Segoe UI", 11, "bold")).grid(row=8, column=0, sticky="w")
        self.concept_list = tk.Listbox(self.source_panel, height=10)
        self.concept_list.grid(row=9, column=0, sticky="nsew", pady=(6, 0))

        self.study_panel = tk.Frame(self, padx=16, pady=16)
        self.study_panel.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=(0, 18))
        self.study_panel.columnconfigure(0, weight=1)
        self.study_panel.rowconfigure(2, weight=1)

        self.theme_canvas = tk.Canvas(self.study_panel, height=105, highlightthickness=0)
        self.theme_canvas.grid(row=0, column=0, sticky="ew")

        self.status_label = tk.Label(self.study_panel, textvariable=self.status_value, anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(12, 10))

        self.mode_frame = tk.Frame(self.study_panel)
        self.mode_frame.grid(row=2, column=0, sticky="nsew")
        self.mode_frame.columnconfigure(0, weight=1)
        self.mode_frame.rowconfigure(0, weight=1)

        self.controls = tk.Frame(self.study_panel)
        self.controls.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        for index in range(5):
            self.controls.columnconfigure(index, weight=1)

        self.cards_button = tk.Button(self.controls, text="Start Cards", command=lambda: self._start_mode("cards"))
        self.practice_button = tk.Button(self.controls, text="Start Practice", command=lambda: self._start_mode("practice"))
        self.test_button = tk.Button(self.controls, text="Start Test", command=lambda: self._start_mode("test"))
        self.again_button = tk.Button(self.controls, text="Study Again", command=self._study_again)
        self.exit_button = tk.Button(self.controls, text="Exit", command=self.destroy)

        self.cards_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.practice_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.test_button.grid(row=0, column=2, sticky="ew", padx=6)
        self.again_button.grid(row=0, column=3, sticky="ew", padx=6)
        self.exit_button.grid(row=0, column=4, sticky="ew", padx=(6, 0))

        self._show_welcome()

    def _add_labeled_option(self, parent: tk.Frame, label: str, variable: tk.StringVar, values: list[str], column: int) -> None:
        tk.Label(parent, text=label).grid(row=0, column=column, padx=(0, 4), sticky="e")
        ttk.OptionMenu(parent, variable, variable.get(), *values).grid(row=0, column=column + 1, sticky="w")

    def _choose_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Choose study source",
            filetypes=[
                ("Study sources", "*.pdf *.pptx *.txt *.md"),
                ("PDF files", "*.pdf"),
                ("PowerPoint files", "*.pptx"),
                ("Text files", "*.txt *.md"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return
        self._run_background("Parsing file...", lambda: parse_file(file_path), self._set_parsed_content)

    def _parse_link(self) -> None:
        url = self.url_value.get().strip()
        if not url:
            messagebox.showinfo("Exam Buddy", "Paste a web link first.")
            return
        self._run_background("Parsing web link...", lambda: parse_url(url), self._set_parsed_content)

    def _parse_pasted_text(self) -> None:
        text = self.paste_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Exam Buddy", "Paste text into the source box first.")
            return
        self._run_background("Parsing pasted text...", lambda: parse_text(text), self._set_parsed_content)

    def _set_parsed_content(self, content) -> None:
        self.parsed_content = content
        self.study_set = None
        self.study_signature = None
        self.concept_list.delete(0, "end")
        for concept in content.concepts:
            self.concept_list.insert("end", concept)
        self.status_value.set(f"Loaded {content.title}. Found {len(content.concepts)} key concepts.")
        self._show_concepts()

    def _start_mode(self, mode: str) -> None:
        if self.parsed_content is None:
            messagebox.showinfo("Exam Buddy", "Load a PDF, PPTX, text, or web link first.")
            return

        signature = (
            tuple(self.parsed_content.concepts),
            self.card_count.get(),
            self.quiz_count.get(),
            self.use_ai.get(),
        )
        if self.study_set is not None and self.study_signature == signature:
            self._show_mode(mode)
            return

        def build_study_set():
            generator = OpenAIStudyGenerator() if self.use_ai.get() else LocalStudyGenerator()
            return generator.generate(
                self.parsed_content.concepts,
                card_count=self.card_count.get(),
                quiz_count=self.quiz_count.get(),
                source_text=self.parsed_content.text,
            )

        def done(study_set) -> None:
            self.study_set = study_set
            self.study_signature = signature
            self._show_mode(mode)

        self._run_background("Generating study material...", build_study_set, done)

    def _show_mode(self, mode: str) -> None:
        self._cancel_timer()
        if mode == "cards":
            self.flashcard_index = 0
            self._render_flashcard(show_answer=False)
        elif mode == "practice":
            self.practice_session = PracticeSession(self.study_set.practice_questions)
            self._render_practice()
        elif mode == "test":
            self.quiz_session = TimedQuizSession(self.study_set.quiz_questions)
            self._render_quiz_question()

    def _study_again(self) -> None:
        self._cancel_timer()
        self.practice_session = None
        self.quiz_session = None
        self.feedback_value.set("")
        if self.parsed_content:
            self._show_concepts()
            self.status_value.set("Choose a study mode to continue.")
        else:
            self._show_welcome()

    def _show_welcome(self) -> None:
        self._clear_mode_frame()
        self.status_value.set("Upload a source, paste text, or parse a web link to begin.")
        tk.Label(
            self.mode_frame,
            text="Load study material, then start flashcards, practice, or a timed test.",
            font=("Segoe UI", 18, "bold"),
            wraplength=620,
            justify="center",
        ).grid(row=0, column=0, sticky="nsew", padx=24, pady=24)

    def _show_concepts(self) -> None:
        self._clear_mode_frame()
        concepts = "\n".join(f"{index + 1}. {concept}" for index, concept in enumerate(self.parsed_content.concepts[:16]))
        tk.Label(
            self.mode_frame,
            text="Key concepts ready",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(20, 8))
        tk.Label(
            self.mode_frame,
            text=concepts,
            font=("Segoe UI", 12),
            justify="left",
            anchor="nw",
        ).grid(row=1, column=0, sticky="nsew", padx=42, pady=16)

    def _render_flashcard(self, show_answer: bool) -> None:
        self._clear_mode_frame()
        cards = self.study_set.flashcards
        card = cards[self.flashcard_index]
        self.status_value.set(f"Flashcards: card {self.flashcard_index + 1} of {len(cards)}")

        card_box = tk.Frame(self.mode_frame, padx=28, pady=28)
        card_box.grid(row=0, column=0, sticky="nsew", padx=36, pady=28)
        card_box.columnconfigure(0, weight=1)
        self._color_widget(card_box, "panel")

        tk.Label(card_box, text=card.question, font=("Segoe UI", 18, "bold"), wraplength=650, justify="center").grid(
            row=0, column=0, sticky="ew", pady=(0, 18)
        )
        answer_text = card.answer if show_answer else "Answer hidden"
        tk.Label(card_box, text=answer_text, font=("Segoe UI", 13), wraplength=680, justify="center").grid(
            row=1, column=0, sticky="ew", pady=(0, 20)
        )

        buttons = tk.Frame(card_box)
        buttons.grid(row=2, column=0)
        self._color_widget(buttons, "panel")
        tk.Button(buttons, text="Previous", command=self._previous_card).grid(row=0, column=0, padx=5)
        tk.Button(buttons, text="Show Answer" if not show_answer else "Hide Answer", command=lambda: self._render_flashcard(not show_answer)).grid(
            row=0, column=1, padx=5
        )
        tk.Button(buttons, text="Next", command=self._next_card).grid(row=0, column=2, padx=5)
        self._apply_theme()

    def _previous_card(self) -> None:
        self.flashcard_index = (self.flashcard_index - 1) % len(self.study_set.flashcards)
        self._render_flashcard(show_answer=False)

    def _next_card(self) -> None:
        self.flashcard_index = (self.flashcard_index + 1) % len(self.study_set.flashcards)
        self._render_flashcard(show_answer=False)

    def _render_practice(self) -> None:
        self._clear_mode_frame()
        session = self.practice_session
        if session is None:
            return

        if session.is_complete:
            self.status_value.set("Practice complete.")
            tk.Label(self.mode_frame, text="Practice complete", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, pady=(32, 8))
            tk.Label(self.mode_frame, text=f"Mastery: {session.mastery_percent}%", font=("Segoe UI", 15)).grid(row=1, column=0)
            return

        question = session.current_question
        self.status_value.set(f"Practice mastery: {session.mastery_percent}%")
        tk.Label(self.mode_frame, text=question.prompt, font=("Segoe UI", 18, "bold"), wraplength=680, justify="center").grid(
            row=0, column=0, sticky="ew", padx=28, pady=(36, 16)
        )
        self.answer_var.set("")
        answer_entry = tk.Entry(self.mode_frame, textvariable=self.answer_var, font=("Segoe UI", 13))
        answer_entry.grid(row=1, column=0, sticky="ew", padx=90)
        answer_entry.focus_set()
        tk.Button(self.mode_frame, text="Submit Answer", command=self._submit_practice_answer).grid(row=2, column=0, pady=14)
        tk.Label(self.mode_frame, textvariable=self.feedback_value, font=("Segoe UI", 12), wraplength=650).grid(
            row=3, column=0, pady=(4, 0)
        )
        self.bind("<Return>", self._practice_return_binding)

    def _practice_return_binding(self, event) -> None:
        if self.practice_session and not self.practice_session.is_complete:
            self._submit_practice_answer()

    def _submit_practice_answer(self) -> None:
        session = self.practice_session
        if session is None or session.is_complete:
            return
        feedback = session.answer_current(self.answer_var.get())
        self.feedback_value.set(feedback.message)
        self._render_practice()

    def _render_quiz_question(self) -> None:
        self._cancel_timer()
        self._clear_mode_frame()
        quiz = self.quiz_session
        if quiz is None:
            return
        question = quiz.current_question
        if question is None:
            self._render_quiz_summary()
            return

        self.answer_var.set("")
        self.mcq_var.set("")
        self.quiz_started_at = perf_counter()
        self.status_value.set(f"Timed quiz: question {quiz.current_index + 1} of {len(quiz.questions)}")

        top = tk.Frame(self.mode_frame)
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 8))
        top.columnconfigure(0, weight=1)
        self._color_widget(top, "bg")
        tk.Label(top, text=question.question_type.replace("_", " ").title(), font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(top, textvariable=self.timer_value, font=("Segoe UI", 13, "bold")).grid(row=0, column=1, sticky="e")

        tk.Label(self.mode_frame, text=question.prompt, font=("Segoe UI", 17, "bold"), wraplength=700, justify="center").grid(
            row=1, column=0, sticky="ew", padx=32, pady=(12, 18)
        )

        answer_area = tk.Frame(self.mode_frame)
        answer_area.grid(row=2, column=0, sticky="ew", padx=88)
        answer_area.columnconfigure(0, weight=1)
        self._color_widget(answer_area, "bg")

        if question.question_type == "mcq":
            for index, option in enumerate(question.options):
                label = f"{chr(ord('A') + index)}. {option}"
                tk.Radiobutton(answer_area, text=label, variable=self.mcq_var, value=chr(ord("A") + index)).grid(
                    row=index, column=0, sticky="w", pady=3
                )
        else:
            tk.Entry(answer_area, textvariable=self.answer_var, font=("Segoe UI", 13)).grid(row=0, column=0, sticky="ew")

        tk.Button(self.mode_frame, text="Submit", command=lambda: self._submit_quiz_answer(auto=False)).grid(row=3, column=0, pady=18)
        self.bind("<Return>", self._quiz_return_binding)
        self._tick_quiz_timer()
        self._apply_theme()

    def _quiz_return_binding(self, event) -> None:
        if self.quiz_session and not self.quiz_session.is_complete:
            self._submit_quiz_answer(auto=False)

    def _tick_quiz_timer(self) -> None:
        quiz = self.quiz_session
        if quiz is None or quiz.current_question is None:
            return
        question = quiz.current_question
        elapsed = int(perf_counter() - self.quiz_started_at)
        remaining = question.timer_seconds - elapsed
        self.timer_value.set(f"{max(0, remaining)} sec")
        if remaining <= 0:
            self._submit_quiz_answer(auto=True)
            return
        self.timer_after_id = self.after(250, self._tick_quiz_timer)

    def _submit_quiz_answer(self, auto: bool) -> None:
        quiz = self.quiz_session
        if quiz is None or quiz.current_question is None:
            return
        self._cancel_timer()
        question = quiz.current_question
        elapsed = min(question.timer_seconds, int(perf_counter() - self.quiz_started_at))
        response = "" if auto else (self.mcq_var.get() if question.question_type == "mcq" else self.answer_var.get())
        quiz.answer_current(response, elapsed_seconds=elapsed)
        self._render_quiz_question()

    def _render_quiz_summary(self) -> None:
        self._clear_mode_frame()
        quiz = self.quiz_session
        if quiz is None:
            return
        summary = quiz.summary()
        minutes, seconds = divmod(summary.elapsed_seconds, 60)
        self.status_value.set("Timed quiz complete.")
        tk.Label(self.mode_frame, text="Quiz Feedback", font=("Segoe UI", 22, "bold")).grid(row=0, column=0, pady=(34, 12))
        tk.Label(
            self.mode_frame,
            text=(
                f"Score: {summary.correct_count}/{summary.total_count} ({summary.score_percent}%)\n"
                f"Mastery: {summary.mastery_percent}%\n"
                f"Timing: {minutes} min {seconds} sec"
            ),
            font=("Segoe UI", 16),
            justify="center",
        ).grid(row=1, column=0, pady=10)
        advice = "Ready to move on." if summary.mastery_percent >= 70 else "Study again, then retry the test."
        tk.Label(self.mode_frame, text=advice, font=("Segoe UI", 13)).grid(row=2, column=0, pady=(8, 0))

    def _run_background(self, message: str, worker, done) -> None:
        self.status_value.set(message)
        self._set_busy(True)

        def target() -> None:
            try:
                result = worker()
            except ParseError as exc:
                self.after(0, lambda: self._show_error(str(exc)))
            except Exception as exc:
                self.after(0, lambda: self._show_error(f"Unexpected error: {exc}"))
            else:
                self.after(0, lambda: self._finish_background(done, result))

        threading.Thread(target=target, daemon=True).start()

    def _finish_background(self, done, result) -> None:
        self._set_busy(False)
        done(result)
        self._apply_theme()

    def _show_error(self, message: str) -> None:
        self._set_busy(False)
        self.status_value.set(message)
        messagebox.showerror("Exam Buddy", message)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (
            self.upload_button,
            self.link_button,
            self.text_button,
            self.cards_button,
            self.practice_button,
            self.test_button,
            self.again_button,
        ):
            button.configure(state=state)

    def _clear_mode_frame(self) -> None:
        self._cancel_timer()
        self.unbind("<Return>")
        for child in self.mode_frame.winfo_children():
            child.destroy()

    def _cancel_timer(self) -> None:
        if self.timer_after_id:
            try:
                self.after_cancel(self.timer_after_id)
            except tk.TclError:
                pass
            self.timer_after_id = None

    def _apply_theme(self) -> None:
        theme = THEMES[self.theme_name.get()]
        self.configure(bg=theme["bg"])
        for widget in (self.header, self.source_panel, self.study_panel, self.mode_frame, self.controls):
            self._color_widget(widget, "bg" if widget in {self.header, self.study_panel, self.mode_frame, self.controls} else "panel")
        self._style_tree(self)
        self._draw_theme_graphics()

    def _style_tree(self, widget) -> None:
        theme = THEMES[self.theme_name.get()]
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=child.master.cget("bg"), fg=theme["text"])
            elif isinstance(child, tk.Button):
                child.configure(
                    bg=theme["accent"],
                    fg=theme["button_text"],
                    activebackground=theme["accent2"],
                    activeforeground=theme["button_text"],
                    relief="flat",
                    padx=10,
                    pady=7,
                )
            elif isinstance(child, tk.Entry):
                child.configure(bg="#ffffff", fg="#111111", insertbackground="#111111", relief="solid")
            elif isinstance(child, tk.Text):
                child.configure(bg="#ffffff", fg="#111111", insertbackground="#111111", relief="solid")
            elif isinstance(child, tk.Listbox):
                child.configure(bg="#ffffff", fg="#111111", selectbackground=theme["accent"], relief="solid")
            elif isinstance(child, tk.Radiobutton):
                child.configure(bg=child.master.cget("bg"), fg=theme["text"], activebackground=child.master.cget("bg"))
            elif isinstance(child, tk.Checkbutton):
                child.configure(bg=child.master.cget("bg"), fg=theme["text"], activebackground=child.master.cget("bg"))
            elif isinstance(child, (tk.Frame, tk.Canvas)):
                pass
            self._style_tree(child)

    def _color_widget(self, widget, color_name: str) -> None:
        widget.configure(bg=THEMES[self.theme_name.get()][color_name])

    def _draw_theme_graphics(self) -> None:
        theme = THEMES[self.theme_name.get()]
        canvas = self.theme_canvas
        canvas.delete("all")
        canvas.configure(bg=theme["panel"])
        width = max(canvas.winfo_width(), 760)
        name = self.theme_name.get()

        if name == "Anime":
            canvas.create_rectangle(0, 0, width, 105, fill=theme["panel"], outline="")
            for x, y, radius, color in [(80, 40, 18, theme["accent"]), (165, 65, 11, theme["accent2"]), (255, 35, 13, theme["accent3"])]:
                canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="")
            for x in range(360, width, 90):
                canvas.create_line(x, 18, x + 34, 52, fill=theme["accent2"], width=3)
                canvas.create_line(x + 34, 18, x, 52, fill=theme["accent2"], width=3)
            canvas.create_text(38, 78, text="Anime focus mode", anchor="w", fill=theme["text"], font=("Segoe UI", 16, "bold"))
        elif name == "Floral":
            canvas.create_rectangle(0, 0, width, 105, fill=theme["panel"], outline="")
            for x in range(70, width, 150):
                for dx, dy in [(0, -16), (16, 0), (0, 16), (-16, 0)]:
                    canvas.create_oval(x + dx - 13, 52 + dy - 13, x + dx + 13, 52 + dy + 13, fill=theme["accent2"], outline="")
                canvas.create_oval(x - 10, 42, x + 10, 62, fill=theme["accent3"], outline="")
                canvas.create_line(x, 65, x, 96, fill=theme["accent"], width=3)
                canvas.create_oval(x + 5, 72, x + 31, 88, fill=theme["accent"], outline="")
            canvas.create_text(38, 24, text="Floral calm mode", anchor="w", fill=theme["text"], font=("Segoe UI", 16, "bold"))
        else:
            canvas.create_rectangle(0, 0, width, 105, fill=theme["panel"], outline="")
            for x in range(0, width, 24):
                for y in range(0, 105, 24):
                    if (x // 24 + y // 24) % 2 == 0:
                        canvas.create_rectangle(x, y, x + 22, y + 22, fill="#263544", outline="")
            for x, color in [(70, theme["accent"]), (104, theme["accent2"]), (138, theme["accent3"])]:
                canvas.create_rectangle(x, 36, x + 24, 60, fill=color, outline="")
            canvas.create_text(190, 50, text="Game-style challenge mode", anchor="w", fill=theme["text"], font=("Consolas", 16, "bold"))


def main() -> None:
    app = ExamBuddyApp()
    app.mainloop()
