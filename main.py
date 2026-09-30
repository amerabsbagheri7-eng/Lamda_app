# -*- coding: utf-8 -*-
"""
اپِ اندرویدِ لمدا — چت + وضعیت/مود، معادلِ همون وب‌سرورِ خودِ ربات.
با Kivy نوشته شده، با کتابخونه‌ی requests به همون endpointهایِ HTTP رباتِ ESP32-S3 وصل می‌شه:
    /chat?msg=...        → پیامِ متنی می‌فرسته، جوابِ لمدا رو برمی‌گردونه
    /moodStatus           → JSON با state, moodScore, online, needsReconciliation, tempC
    /state?mode=...        → دستورِ مستقیمِ تغییرِ حالت (happy/sad/angry/...)
    /setOnline?value=0/1   → آنلاین/آفلاین کردنِ ربات از راه دور

قبل از اجرا آدرسِ IP رباتت رو تو تنظیماتِ اپ (پایینِ صفحه، فیلدِ آدرس) وارد کن،
یا مستقیم متغیرِ DEFAULT_HOST رو پایین‌تر عوض کن.
"""

import threading
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen

DEFAULT_HOST = "192.168.1.50"  # آی‌پیِ پیش‌فرضِ ربات — از رو سریال مانیتور یا روتر پیدا کن
REQUEST_TIMEOUT = 6  # ثانیه

STATE_LABELS_FA = {
    "NORMAL": "عادی 🙂", "HAPPY": "خوشحال 😄", "ANGRY": "عصبانی 😠",
    "SLEEP": "خواب 😴", "THINKING": "درحالِ فکر 🤔", "FLIRT": "ناز‌کشی 🥰",
    "SURPRISED": "متعجب 😲", "SHY": "خجالتی ☺️", "PLAYING": "درحالِ بازی 🎮",
    "SAD": "غمگین 😢", "WORRIED": "نگران 😟", "SKEPTICAL": "شکاک 🧐",
    "DIZZY": "گیج 😵", "WAKE_GRUMPY": "تازه‌بیدار 😑", "ANNOYED": "کلافه 😒",
    "SPONTANEOUS_SAD": "غمگینِ خودجوش 😭", "SPONTANEOUS_HAPPY": "خوشحالِ خودجوش 😁",
}

KV = """
#:import dp kivy.metrics.dp

<RootLayout>:
    orientation: "vertical"
    padding: dp(10)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: 0.10, 0.10, 0.18, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(8)

        Label:
            text: "لمدا"
            font_size: "22sp"
            bold: True
            color: 1, 1, 1, 1

        Label:
            id: conn_label
            text: root.conn_text
            color: (0.3, 0.9, 0.4, 1) if root.is_online else (0.9, 0.3, 0.3, 1)
            font_size: "14sp"

    # ---- کارتِ وضعیت/مود ----
    BoxLayout:
        size_hint_y: None
        height: dp(90)
        padding: dp(10)
        spacing: dp(4)
        orientation: "vertical"
        canvas.before:
            Color:
                rgba: 1, 1, 1, 0.06
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(14)]

        Label:
            text: "حالتِ فعلی: " + root.state_text
            color: 1, 1, 1, 1
            font_size: "16sp"
            halign: "right"
            text_size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(20)
            Label:
                text: "خلق‌وخو"
                color: 0.8, 0.8, 0.85, 1
                font_size: "12sp"
                size_hint_x: None
                width: dp(60)
            ProgressBar:
                id: mood_bar
                max: 100
                value: root.mood_display
            Label:
                text: str(int(root.mood_score))
                color: 0.8, 0.8, 0.85, 1
                font_size: "12sp"
                size_hint_x: None
                width: dp(36)

        Label:
            text: ("قهره، نیاز به ناز داره 🥺" if root.needs_reconciliation else "دمای بدنه: %.1f°C" % root.temp_c)
            color: (0.95, 0.6, 0.2, 1) if root.needs_reconciliation else (0.7, 0.7, 0.75, 1)
            font_size: "12sp"
            halign: "right"
            text_size: self.size

    # ---- دکمه‌هایِ سریعِ تغییرِ حالت ----
    ScrollView:
        size_hint_y: None
        height: dp(48)
        do_scroll_y: False
        BoxLayout:
            id: quick_state_row
            size_hint_x: None
            width: self.minimum_width
            spacing: dp(6)
            padding: [0, 0, 0, 0]

    # ---- تاریخچه‌ی چت ----
    ScrollView:
        id: chat_scroll
        BoxLayout:
            id: chat_box
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(6)
            padding: dp(4)

    # ---- ردیفِ ورودی ----
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(6)

        TextInput:
            id: msg_input
            hint_text: "پیامت رو بنویس..."
            multiline: False
            font_size: "15sp"
            on_text_validate: root.send_message()

        Button:
            text: "ارسال"
            size_hint_x: None
            width: dp(70)
            on_release: root.send_message()

    # ---- تنظیماتِ آدرسِ ربات ----
    BoxLayout:
        size_hint_y: None
        height: dp(40)
        spacing: dp(6)

        TextInput:
            id: host_input
            text: root.host
            hint_text: "آیِ‌پیِ لمدا (مثلاً 192.168.1.50)"
            multiline: False
            font_size: "13sp"

        Button:
            text: "اتصال"
            size_hint_x: None
            width: dp(70)
            on_release: root.apply_host(host_input.text)

        Button:
            text: "آنلاین"
            size_hint_x: None
            width: dp(70)
            background_color: (0.2, 0.6, 0.3, 1)
            on_release: root.set_online(True)

        Button:
            text: "آفلاین"
            size_hint_x: None
            width: dp(70)
            background_color: (0.5, 0.25, 0.25, 1)
            on_release: root.set_online(False)
"""


class ChatBubble(BoxLayout):
    """یه حبابِ چت ساده — پیامِ کاربر یا جوابِ لمدا."""

    text = StringProperty("")
    is_user = BooleanProperty(False)


class RootLayout(BoxLayout):
    host = StringProperty(DEFAULT_HOST)
    state_text = StringProperty("نامشخص")
    mood_score = NumericProperty(0)
    mood_display = NumericProperty(50)  # 0..100 برایِ ProgressBar (moodScore تقریباً -50..50 هست)
    temp_c = NumericProperty(0.0)
    is_online = BooleanProperty(False)
    conn_text = StringProperty("در حالِ اتصال...")
    needs_reconciliation = BooleanProperty(False)

    QUICK_STATES = [
        ("happy", "خوشحال"), ("love", "ناز"), ("sad", "غمگین"),
        ("angry", "عصبانی"), ("surprise", "تعجب"), ("sleep", "خواب"),
        ("think", "فکر"), ("normal", "عادی"),
    ]

    def on_kv_post(self, base_widget):
        for mode, label in self.QUICK_STATES:
            btn = self._make_state_button(mode, label)
            self.ids.quick_state_row.add_widget(btn)
        self._add_bubble("سلام! من لمدام 🙂 هر وقت خواستی باهام حرف بزن.", is_user=False)
        Clock.schedule_interval(self._poll_status, 4)
        self._poll_status(0)

    def _make_state_button(self, mode, label):
        from kivy.uix.button import Button
        from kivy.metrics import dp

        btn = Button(text=label, size_hint_x=None, width=dp(64))
        btn.bind(on_release=lambda *_: self.send_state(mode))
        return btn

    # ---------------- شبکه (تو یه ترد جدا، تا UI فریز نشه) ----------------

    def apply_host(self, new_host):
        new_host = new_host.strip()
        if new_host:
            self.host = new_host
            self._poll_status(0)

    def _base_url(self):
        return "http://{}".format(self.host)

    def _poll_status(self, dt):
        threading.Thread(target=self._poll_status_worker, daemon=True).start()

    def _poll_status_worker(self):
        try:
            r = requests.get(self._base_url() + "/moodStatus", timeout=REQUEST_TIMEOUT)
            data = r.json()
            Clock.schedule_once(lambda dt: self._apply_status(data))
        except Exception:
            Clock.schedule_once(lambda dt: self._apply_conn_failed())

    def _apply_status(self, data):
        self.is_online = bool(data.get("online"))
        self.conn_text = "متصل" if True else "قطع"  # اتصال به خودِ ربات برقراره (جوابِ HTTP اومده)
        self.conn_text = "متصل به ربات"
        state = data.get("state", "NORMAL")
        self.state_text = STATE_LABELS_FA.get(state, state)
        self.mood_score = data.get("moodScore", 0)
        self.mood_display = max(0, min(100, self.mood_score + 50))
        self.temp_c = data.get("tempC", 0.0)
        self.needs_reconciliation = bool(data.get("needsReconciliation"))

    def _apply_conn_failed(self):
        self.conn_text = "به ربات وصل نمی‌شه ⚠️"
        self.is_online = False

    def send_message(self):
        text = self.ids.msg_input.text.strip()
        if not text:
            return
        self.ids.msg_input.text = ""
        self._add_bubble(text, is_user=True)
        threading.Thread(target=self._send_message_worker, args=(text,), daemon=True).start()

    def _send_message_worker(self, text):
        try:
            r = requests.get(
                self._base_url() + "/chat",
                params={"msg": text},
                timeout=REQUEST_TIMEOUT,
            )
            reply = r.text
        except Exception:
            reply = "⚠️ نتونستم به لمدا وصل بشم. آدرسِ آی‌پی رو چک کن."
        Clock.schedule_once(lambda dt: self._add_bubble(reply, is_user=False))

    def send_state(self, mode):
        threading.Thread(target=self._send_state_worker, args=(mode,), daemon=True).start()

    def _send_state_worker(self, mode):
        try:
            requests.get(
                self._base_url() + "/state",
                params={"mode": mode},
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            pass
        Clock.schedule_once(self._poll_status)

    def set_online(self, value):
        threading.Thread(target=self._set_online_worker, args=(value,), daemon=True).start()

    def _set_online_worker(self, value):
        try:
            requests.get(
                self._base_url() + "/setOnline",
                params={"value": 1 if value else 0},
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            pass
        Clock.schedule_once(self._poll_status)

    def _add_bubble(self, text, is_user):
        from kivy.uix.label import Label
        from kivy.metrics import dp

        row = BoxLayout(size_hint_y=None, height=dp(36), padding=[dp(6), 0])
        lbl = Label(
            text=text,
            color=(1, 1, 1, 1) if not is_user else (0.85, 0.95, 1, 1),
            halign="right",
            valign="middle",
            text_size=(None, None),
        )
        lbl.bind(texture_size=lambda inst, val: setattr(row, "height", max(dp(36), val[1] + dp(10))))
        lbl.text_size = (self.width * 0.75 if self.width else 260, None)
        row.add_widget(lbl)
        self.ids.chat_box.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self.ids.chat_scroll, "scroll_y", 0))


class LamdaApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootLayout()


if __name__ == "__main__":
    LamdaApp().run()
