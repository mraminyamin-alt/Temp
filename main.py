import os
import re
import sqlite3
import threading
import secrets
import string
from datetime import datetime

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

API = "https://api.mail.tm"
DB_NAME = "tempmail.db"


class TempMailApp(App):
    def build(self):
        self.title = "TempMail Pro"
        self.db_path = os.path.join(self.user_data_dir, DB_NAME)
        self.init_db()
        self.selected_box = None

        self.root_box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.header = Label(text="[b][color=9b8cff]TempMail Pro[/color][/b]\n[color=bbbbdd]ایمیل موقت شخصی[/color]",
                            markup=True, size_hint_y=None, height=dp(75), font_size="21sp")
        self.root_box.add_widget(self.header)

        self.status = Label(text="آماده", size_hint_y=None, height=dp(30), color=(0.7,0.85,1,1))
        self.root_box.add_widget(self.status)

        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.new_btn = Button(text="ساخت ایمیل")
        self.new_btn.bind(on_press=self.create_email)
        self.refresh_btn = Button(text="تازه‌سازی")
        self.refresh_btn.bind(on_press=self.refresh_inbox)
        actions.add_widget(self.new_btn)
        actions.add_widget(self.refresh_btn)
        self.root_box.add_widget(actions)

        self.address_label = Label(text="هنوز ایمیلی انتخاب نشده", size_hint_y=None,
                                   height=dp(55), halign="center", valign="middle")
        self.address_label.bind(size=lambda *_: setattr(self.address_label, "text_size", self.address_label.size))
        self.root_box.add_widget(self.address_label)

        self.copy_btn = Button(text="کپی آدرس", size_hint_y=None, height=dp(42))
        self.copy_btn.bind(on_press=self.copy_address)
        self.root_box.add_widget(self.copy_btn)

        self.scroll = ScrollView()
        self.items = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(7), padding=dp(3))
        self.items.bind(minimum_height=self.items.setter("height"))
        self.scroll.add_widget(self.items)
        self.root_box.add_widget(self.scroll)

        self.show_boxes()
        return self.root_box

    def init_db(self):
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS boxes
                (id TEXT PRIMARY KEY, address TEXT, token TEXT, created_at TEXT)""")

    def db_boxes(self):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            return [dict(x) for x in con.execute(
                "SELECT * FROM boxes ORDER BY created_at DESC").fetchall()]

    def set_status(self, msg):
        self.status.text = msg

    def popup(self, title, message):
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        lbl = Label(text=message)
        content.add_widget(lbl)
        btn = Button(text="بستن", size_hint_y=None, height=dp(44))
        content.add_widget(btn)
        pop = Popup(title=title, content=content, size_hint=(.9, .45))
        btn.bind(on_press=pop.dismiss)
        pop.open()

    def api_get(self, path, token=None):
        headers = {"Authorization": "Bearer " + token} if token else {}
        r = requests.get(API + path, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def create_email(self, *_):
        self.set_status("در حال ساخت ایمیل...")
        self.new_btn.disabled = True
        threading.Thread(target=self._create_email, daemon=True).start()

    def _create_email(self):
        try:
            data = self.api_get("/domains")
            domains = data if isinstance(data, list) else data.get("hydra:member", [])
            active = [d.get("domain") for d in domains
                      if isinstance(d, dict) and d.get("isActive") and d.get("domain")]
            if not active:
                raise Exception("دامنه فعالی پیدا نشد")
            username = "user" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))
            address = username + "@" + active[0]
            password = secrets.token_urlsafe(20)

            r = requests.post(API + "/accounts",
                              json={"address": address, "password": password}, timeout=30)
            r.raise_for_status()
            r = requests.post(API + "/token",
                              json={"address": address, "password": password}, timeout=30)
            r.raise_for_status()
            token = r.json()["token"]
            box_id = secrets.token_urlsafe(16)
            created = datetime.now().strftime("%Y-%m-%d %H:%M")
            with sqlite3.connect(self.db_path) as con:
                con.execute("INSERT INTO boxes VALUES (?, ?, ?, ?)",
                            (box_id, address, token, created))
            Clock.schedule_once(lambda dt: self._created(box_id, address), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self._error(err), 0)

    def _created(self, box_id, address):
        self.new_btn.disabled = False
        self.selected_box = self.get_box(box_id)
        self.address_label.text = address
        self.set_status("ایمیل ساخته شد")
        self.show_boxes()
        self.refresh_inbox()

    def _error(self, err):
        self.new_btn.disabled = False
        self.set_status("خطا در ساخت ایمیل")
        self.popup("خطا", err)

    def get_box(self, box_id):
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT * FROM boxes WHERE id=?", (box_id,)).fetchone()
            return dict(row) if row else None

    def show_boxes(self):
        self.items.clear_widgets()
        boxes = self.db_boxes()
        if not boxes:
            self.items.add_widget(Label(text="هنوز ایمیلی نساخته‌ای", size_hint_y=None, height=dp(50)))
        for box in boxes:
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(5))
            choose = Button(text=box["address"], halign="center")
            choose.bind(on_press=lambda btn, bid=box["id"]: self.select_box(bid))
            delete = Button(text="حذف", size_hint_x=.25, background_color=(.65,.2,.3,1))
            delete.bind(on_press=lambda btn, bid=box["id"]: self.delete_box(bid))
            row.add_widget(choose)
            row.add_widget(delete)
            self.items.add_widget(row)

    def select_box(self, box_id):
        self.selected_box = self.get_box(box_id)
        if self.selected_box:
            self.address_label.text = self.selected_box["address"]
            self.set_status("صندوق انتخاب شد")
            self.refresh_inbox()

    def copy_address(self, *_):
        if self.selected_box:
            Clipboard.copy(self.selected_box["address"])
            self.set_status("آدرس کپی شد")
        else:
            self.popup("توجه", "ابتدا یک ایمیل بساز یا انتخاب کن.")

    def delete_box(self, box_id):
        with sqlite3.connect(self.db_path) as con:
            con.execute("DELETE FROM boxes WHERE id=?", (box_id,))
        if self.selected_box and self.selected_box["id"] == box_id:
            self.selected_box = None
            self.address_label.text = "هنوز ایمیلی انتخاب نشده"
        self.show_boxes()
        self.set_status("از فهرست برنامه حذف شد؛ حساب سرور حذف نشده است.")

    def refresh_inbox(self, *_):
        if not self.selected_box:
            self.set_status("ابتدا یک ایمیل انتخاب کن")
            return
        self.set_status("در حال دریافت پیام‌ها...")
        threading.Thread(target=self._load_messages, daemon=True).start()

    def _load_messages(self):
        try:
            data = self.api_get("/messages", self.selected_box["token"])
            msgs = data.get("hydra:member", [])
            Clock.schedule_once(lambda dt, items=msgs: self._show_messages(items), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self._error(err), 0)

    def _show_messages(self, messages):
        self.items.clear_widgets()
        if not messages:
            self.items.add_widget(Label(text="هنوز ایمیلی دریافت نشده است",
                                        size_hint_y=None, height=dp(55)))
        for msg in messages:
            sender = (msg.get("from") or {}).get("address", "نامشخص")
            subject = msg.get("subject") or "بدون موضوع"
            btn = Button(text=subject + "\n" + sender, size_hint_y=None, height=dp(65))
            btn.bind(on_press=lambda b, mid=msg["id"]: self.open_message(mid))
            self.items.add_widget(btn)
        self.set_status(f"{len(messages)} پیام")

    def open_message(self, message_id):
        self.set_status("در حال باز کردن پیام...")
        threading.Thread(target=self._load_message, args=(message_id,), daemon=True).start()

    def _load_message(self, message_id):
        try:
            detail = self.api_get("/messages/" + message_id, self.selected_box["token"])
            body = detail.get("text") or ""
            if isinstance(body, list):
                body = "\n".join(str(x) for x in body)
            subject = detail.get("subject") or "بدون موضوع"
            codes = list(dict.fromkeys(re.findall(r"(?<!\d)\d{4,8}(?!\d)", subject + "\n" + body)))
            sender = (detail.get("from") or {}).get("address", "نامشخص")
            result = (subject, sender, body, codes)
            Clock.schedule_once(lambda dt, x=result: self._show_message(x), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt, err=str(e): self._error(err), 0)

    def _show_message(self, result):
        subject, sender, body, codes = result
        text = f"موضوع: {subject}\nفرستنده: {sender}\n\n{body}\n\nکدهای احتمالی: {', '.join(codes) if codes else 'پیدا نشد'}"
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        view = TextInput(text=text, readonly=True, multiline=True)
        content.add_widget(view)
        if codes:
            copy = Button(text="کپی اولین کد: " + codes[0], size_hint_y=None, height=dp(45))
            copy.bind(on_press=lambda *_: self.copy_code(codes[0]))
            content.add_widget(copy)
        close = Button(text="بستن", size_hint_y=None, height=dp(45))
        content.add_widget(close)
        pop = Popup(title="پیام ایمیل", content=content, size_hint=(.94, .85))
        close.bind(on_press=pop.dismiss)
        pop.open()
        self.set_status("پیام باز شد")

    def copy_code(self, code):
        Clipboard.copy(code)
        self.set_status("کد کپی شد")


if __name__ == "__main__":
    TempMailApp().run()