# client_hunter/app/message_generator/generator.py

def generate_message(name, category, website, score):
    """
    Simple pitch generator used by auto-sender.
    You can customize tone and length here.
    """

    # If no website → highlight opportunity
    if not website:
        return (
            f"Hi {name},\n\n"
            f"I noticed your {category} business doesn't have a website yet. "
            "I build modern and professional websites that help businesses get more customers online.\n\n"
            "If you're interested, I can show you a quick demo version. "
            "Let me know — happy to help!\n\n"
            "— Faraz"
        )

    # If free-host or broken → improvement pitch
    if website and ("wix" in website or "wordpress" in website or "blogspot" in website):
        return (
            f"Hi {name},\n\n"
            "I saw your current website is using a free hosting platform. "
            "I can rebuild a faster, more professional version that attracts more customers.\n\n"
            "Want to see a sample? I can share instantly.\n\n"
            "— Faraz"
        )

    if score >= 90:
        return (
            f"Hi {name},\n\n"
            "Your online presence seems low or incomplete, which means you're missing customers "
            "searching for services like yours.\n\n"
            "I build high-converting business websites at affordable prices. "
            "Would you like a free demo?\n\n"
            "— Faraz"
        )

    # Fallback generic message
    return (
        f"Hi {name},\n\n"
        "I help businesses like yours build modern websites to increase customer flow. "
        "If you'd like a quick demo, I can create one today.\n\n"
        "— Faraz"
    )
