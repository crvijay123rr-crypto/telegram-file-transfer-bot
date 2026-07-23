# Advanced Telegram File Transfer Bot 🚀

An advanced, feature-rich Telegram File Transfer & Clone Bot built with **Python**, **Telethon**, and **MongoDB**. Designed for seamless bulk media/file transferring across chats and channels with custom Find & Replace text rules and robust session management.

---

## ✨ Features

* **🔐 Multi-Session User Login:** Secure interactive user authentication via phone number, OTP, and 2-step verification (`/login`).
* **🔄 Bulk Content Cloning:** Clone files, videos, documents, photos, and texts from a specified source range to any destination channel/group.
* **⚡ Smart Checkpoint & Resume:** Powered by MongoDB, it maintains live task states allowing you to pause, stop, and retry seamlessly.
* **🛡️ Strict Permission & Admin Check:** Validates admin rights and posting permissions in destination channels before executing transfers, prompting a retry option if restricted.
* **✏️ Find & Replace Custom Rules:** Automatically apply custom regex or find/replace rules on filenames and message captions on-the-fly.
* **🧹 Clean Caption Parsing:** Strips unwanted raw markdown wrappers and formatting artifacts for clean output.
* **👑 Subscription & Admin Panel:** Integrated free/premium user tier system with admin approval workflows.

---

## 🛠️ Prerequisites & Requirements

* Python 3.8+
* MongoDB database instance
* Telegram API ID and API Hash (from [my.telegram.org](https://my.telegram.org))
* Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

---

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-username/telegram-file-transfer-bot.git](https://github.com/your-username/telegram-file-transfer-bot.git)
   cd telegram-file-transfer-bot
   
