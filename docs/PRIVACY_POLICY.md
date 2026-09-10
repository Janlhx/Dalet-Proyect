# Privacy Policy — Dalet Bot

**Last Updated:** September 2026

This Privacy Policy explains how **Dalet** ( the Bot, we, us) collects, uses, stores, and protects user information when you interact with the Bot on Discord.

---

### 1. Information We Collect
To provide core functionality, Dalet collects and processes minimal data:

1. **Discord Identifiers**:
   - **User IDs**: To associate linked osu! accounts, personal reminders, and user preferences.
   - **Server (Guild) & Channel IDs**: To store channel locks, server settings, and deliver scheduled reminders.
   - **Usernames & Nicknames**: To display scores and user statistics in embeds.

2. **osu! Account Data**:
   - When you link your account using /link, we store your public osu! username and User ID.
   - We query public statistics (PP, rank, accuracy, best scores) directly from the official public osu! API (Bancho).

3. **Message Context (AI Interactions)**:
   - When you explicitly mention @Dalet or use conversational commands, the content of your message and immediately relevant chat history are processed in real-time to generate a contextual response.
   - Chat logs stored in server history are only retained for server lore / summary features if configured by the server.

---

### 2. How We Use Your Information
We use the collected information exclusively to:
- Deliver requested bot commands (e.g., displaying your profile, skills breakdown, or server leaderboard).
- Trigger scheduled reminders you have set.
- Generate contextual AI responses with Dalet's custom persona.
- Maintain operational stability and diagnose technical errors.

We **NEVER** sell, rent, monetize, or share your personal data with third-party advertising companies.

---

### 3. Data Storage & Security
- Data is stored securely in encrypted databases (Turso Cloud / SQLite).
- Access to production databases is strictly restricted to the bot developer.
- We implement industry-standard safeguards to prevent unauthorized access or disclosure.

---

### 4. Third-Party Services
Dalet integrates with reputable external APIs to fulfill specific features:
- **Discord API**: Core bot gateway and interactions.
- **ppy.sh (osu! API v2)**: Public beatmap and player statistics.
- **AI Inference Providers (DeepSeek, Google Gemini, Groq)**: Stateless API calls to process conversational queries. Message content passed to these APIs is subject to their respective data processing standards and is not used to train public models.

---

### 5. Data Retention & Deletion (Right to be Forgotten)
You have full control over your data:
- **Unlinking osu! Account**: You can unlink your account at any time using /link or by contacting us.
- **Complete Data Erasure**: If you wish to permanently delete all data associated with your Discord User ID (reminders, links, logs), please contact the developer via Discord or GitHub. All records will be deleted promptly within 48 hours.

---

### 6. Changes to This Policy
We may update this Privacy Policy from time to time. Any significant updates will be noted in the Bot's changelog (d.changelog).

---

### 7. Contact
For any privacy-related inquiries, requests, or questions:
- **Developer / Maintainer**: Litxe
- **Discord**: @Litxe
- **GitHub**: [Dalet-Proyect](https://github.com/Janlhx/Dalet-Proyect)
