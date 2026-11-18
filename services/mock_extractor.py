"""Mock extractor for offline demo mode and sample packs.
Ensures the system works 100% out of the box even without an API key.
"""
from __future__ import annotations

import json
import re
from typing import Any


def _pack1_data() -> dict:
    return {
        "messages": [
            {"id": "M1", "sender": "Registrar's office", "date": "2026-03-02", "auth": 3, "relevant": True},
            {"id": "M2", "sender": "Skyline Convention Centre", "date": "2026-02-25", "auth": 2, "relevant": True},
            {"id": "M3", "sender": "Food vendor", "date": "2026-03-01", "auth": 2, "relevant": True},
            {"id": "M4", "sender": "Food vendor", "date": "2026-03-04", "auth": 2, "relevant": True},
            {"id": "M5", "sender": "Judging lead", "date": "2026-03-03", "auth": 2, "relevant": True},
            {"id": "M6", "sender": "Accounts", "date": "2026-03-03", "auth": 3, "relevant": True},
            {"id": "M7", "sender": "Cricket club", "date": "2026-03-02", "auth": 1, "relevant": False, "why": "cricket practice"},
            {"id": "M8", "sender": "Volunteer", "date": "2026-03-05", "auth": 1, "relevant": True},
        ],
        "claims": [
            {"m": "M1", "k": "students", "v": 96, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "team_size", "v": 4, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "budget_total", "v": 480000, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "staff", "v": 10, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "event_duration_minutes", "v": 300, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "venue_requirement", "v": "wheelchair_access", "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "break_required", "s": "lunch", "v": 30, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "break_required", "s": "prayer", "v": 20, "st": "confirmed", "c": 1.0},
            
            {"m": "M2", "k": "venue_capacity", "s": "Orchid Room", "v": 90, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Orchid Room", "v": 60000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_capacity", "s": "Jasmine Hall", "v": 140, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Jasmine Hall", "v": 95000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_feature", "s": "Jasmine Hall", "v": "wheelchair_access", "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_capacity", "s": "Lotus Hall", "v": 180, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Lotus Hall", "v": 130000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_feature", "s": "Lotus Hall", "v": "wheelchair_access", "st": "confirmed", "c": 1.0},
            
            {"m": "M3", "k": "food_price_per_head", "s": "Biryani box", "v": 950, "st": "superseded", "c": 1.0},
            {"m": "M3", "k": "food_price_per_head", "s": "Sandwich box", "v": 600, "st": "confirmed", "c": 1.0},
            {"m": "M3", "k": "food_delivery_fee", "s": "Food vendor", "v": 5000, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "food_price_per_head", "s": "Biryani box", "v": 1050, "st": "corrected", "sup": "M3", "c": 1.0},
            
            {"m": "M5", "k": "judges_available", "v": 10, "st": "confirmed", "c": 1.0},
            {"m": "M5", "k": "judge_honorarium", "v": 4000, "st": "confirmed", "c": 1.0},
            {"m": "M5", "k": "judge_minutes_per_team", "v": 20, "st": "confirmed", "c": 1.0},
            {"m": "M5", "k": "judge_max_teams", "v": 4, "st": "confirmed", "c": 1.0},
            
            {"m": "M6", "k": "expense_committed", "s": "trophies", "v": 45000, "st": "confirmed", "c": 1.0},
            {"m": "M6", "k": "expense_committed", "s": "T-shirts", "v": 60000, "st": "confirmed", "c": 1.0},
            {"m": "M8", "k": "expense_proposed", "s": "photographer", "v": 25000, "st": "proposed", "c": 0.7, "why": "volunteer proposal"},
        ]
    }


def _pack2_data() -> dict:
    return {
        "messages": [
            {"id": "M1", "sender": "Office of Student Affairs", "date": "2026-10-12", "auth": 3, "relevant": True},
            {"id": "M2", "sender": "Venue manager", "date": "2026-10-08", "auth": 2, "relevant": True},
            {"id": "M3", "sender": "Student Affairs", "date": "2026-10-13", "auth": 3, "relevant": True},
            {"id": "M4", "sender": "Karachi Foods", "date": "2026-10-05", "auth": 2, "relevant": True},
            {"id": "M5", "sender": "Karachi Foods", "date": "2026-10-11", "auth": 2, "relevant": True},
            {"id": "M6", "sender": "Jury coordinator", "date": "2026-10-09", "auth": 2, "relevant": True},
            {"id": "M7", "sender": "Accounts", "date": "2026-10-10", "auth": 3, "relevant": True},
            {"id": "M8", "sender": "Media club", "date": "2026-10-12", "auth": 1, "relevant": True},
            {"id": "M9", "sender": "Someone", "date": None, "auth": 1, "relevant": False, "why": "parking query"},
        ],
        "claims": [
            {"m": "M1", "k": "students", "v": 132, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "team_size", "v": 4, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "budget_total", "v": 410000, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "staff", "v": 12, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "attendee_group", "s": "guests", "v": 25, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "cap", "s": "food_cost", "v": 160000, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "event_duration_minutes", "v": 240, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "break_required", "s": "Zuhr", "v": 20, "st": "confirmed", "c": 1.0},
            
            {"m": "M2", "k": "venue_capacity", "s": "Hall X", "v": 180, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Hall X", "v": 70000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_capacity", "s": "Hall Y", "v": 220, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Hall Y", "v": 95000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_feature", "s": "Hall Y", "v": "backup_power", "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_capacity", "s": "Hall Z", "v": 300, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Hall Z", "v": 140000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_feature", "s": "Hall Z", "v": "backup_power", "st": "confirmed", "c": 1.0},
            
            {"m": "M3", "k": "venue_requirement", "v": "backup_power", "st": "confirmed", "c": 1.0},
            
            {"m": "M4", "k": "food_price_per_head", "s": "Chicken wrap meal", "v": 700, "st": "superseded", "c": 1.0},
            {"m": "M4", "k": "food_price_per_head", "s": "Deluxe platter", "v": 1150, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "food_delivery_fee", "s": "Karachi Foods", "v": 3000, "st": "confirmed", "c": 1.0},
            {"m": "M5", "k": "food_price_per_head", "s": "Chicken wrap meal", "v": 760, "st": "corrected", "sup": "M4", "c": 1.0},
            
            {"m": "M6", "k": "judges_available", "v": 14, "st": "confirmed", "c": 1.0},
            {"m": "M6", "k": "judge_honorarium", "v": 6000, "st": "confirmed", "c": 1.0},
            {"m": "M6", "k": "judge_minutes_per_team", "v": 12, "st": "confirmed", "c": 1.0},
            {"m": "M6", "k": "judge_max_teams", "v": 3, "st": "confirmed", "c": 1.0},
            
            {"m": "M7", "k": "expense_committed", "s": "lanyards", "v": 18000, "st": "confirmed", "c": 1.0},
            {"m": "M7", "k": "expense_committed", "s": "prizes", "v": 75000, "st": "confirmed", "c": 1.0},
            {"m": "M8", "k": "expense_proposed", "s": "drone videographer", "v": 35000, "st": "proposed", "c": 0.7, "why": "media club proposal"},
        ]
    }


def _pack3_data() -> dict:
    return {
        "messages": [
            {"id": "M1", "sender": "Principal's Secretariat", "date": "2026-12-01", "auth": 3, "relevant": True},
            {"id": "M2", "sender": "City Banquets", "date": "2026-11-28", "auth": 2, "relevant": True},
            {"id": "M3", "sender": "Desi Kitchen", "date": "2026-11-29", "auth": 2, "relevant": True},
            {"id": "M4", "sender": "Judges panel coordinator", "date": "2026-11-30", "auth": 2, "relevant": True},
            {"id": "M5", "sender": "Ali", "date": "2026-12-02", "auth": 1, "relevant": False, "why": "chat about match"},
            {"id": "M6", "sender": "Treasurer", "date": "2026-11-30", "auth": 3, "relevant": True},
        ],
        "claims": [
            {"m": "M1", "k": "students", "v": 120, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "team_size", "v": 5, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "budget_total", "v": 300000, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "staff", "v": 8, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "event_duration_minutes", "v": 180, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "food_requirement", "v": "vegetarian", "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "venue_requirement", "v": "projector", "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "break_required", "s": "Zuhr namaz", "v": 15, "st": "confirmed", "c": 1.0},
            
            {"m": "M2", "k": "venue_capacity", "s": "Hall Rose", "v": 150, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Hall Rose", "v": 70000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_feature", "s": "Hall Rose", "v": "projector", "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_capacity", "s": "Hall Tulip", "v": 200, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Hall Tulip", "v": 50000, "st": "confirmed", "c": 1.0},
            
            {"m": "M3", "k": "food_price_per_head", "s": "Veg thali", "v": 900, "st": "confirmed", "c": 1.0},
            {"m": "M3", "k": "food_feature", "s": "Veg thali", "v": "vegetarian", "st": "confirmed", "c": 1.0},
            {"m": "M3", "k": "food_price_per_head", "s": "chicken karahi box", "v": 1100, "st": "confirmed", "c": 1.0},
            
            {"m": "M4", "k": "judges_available", "v": 8, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "judge_honorarium", "v": 3000, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "judge_minutes_per_team", "v": 12, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "judge_max_teams", "v": 4, "st": "confirmed", "c": 1.0},
            
            {"m": "M6", "k": "expense_committed", "s": "certificates", "v": 12000, "st": "confirmed", "c": 1.0},
            {"m": "M6", "k": "expense_committed", "s": "internet", "v": 15000, "st": "confirmed", "c": 1.0},
        ]
    }


def _pack4_data() -> dict:
    return {
        "messages": [
            {"id": "M1", "sender": "Vice Chancellor office", "date": "2026-04-05", "auth": 3, "relevant": True},
            {"id": "M2", "sender": "Hotel Serena events", "date": "2026-04-01", "auth": 2, "relevant": True},
            {"id": "M3", "sender": "Caterer Bismillah", "date": "2026-04-02", "auth": 2, "relevant": True},
            {"id": "M4", "sender": "Judging head", "date": "2026-04-03", "auth": 2, "relevant": True},
            {"id": "M5", "sender": "Admin", "date": "2026-04-04", "auth": 3, "relevant": True},
            {"id": "M6", "sender": "Unknown", "date": "2026-04-06", "auth": 1, "relevant": False, "why": "prize spam"},
        ],
        "claims": [
            {"m": "M1", "k": "students", "v": 72, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "team_size", "v": 3, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "budget_total", "v": 260000, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "staff", "v": 4, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "event_duration_minutes", "v": 240, "st": "confirmed", "c": 1.0},
            {"m": "M1", "k": "break_required", "s": "tea", "v": 10, "st": "confirmed", "c": 1.0},
            
            {"m": "M2", "k": "venue_capacity", "s": "Marquee", "v": 120, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Marquee", "v": 45000, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_capacity", "s": "Ballroom", "v": 250, "st": "confirmed", "c": 1.0},
            {"m": "M2", "k": "venue_price", "s": "Ballroom", "v": 90000, "st": "confirmed", "c": 1.0},
            
            {"m": "M3", "k": "food_price_per_head", "s": "Lunch pack", "v": 750, "st": "confirmed", "c": 1.0},
            
            {"m": "M4", "k": "judges_available", "v": 6, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "judge_honorarium", "v": 2500, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "judge_minutes_per_team", "v": 10, "st": "confirmed", "c": 1.0},
            {"m": "M4", "k": "judge_max_teams", "v": 4, "st": "confirmed", "c": 1.0},
            
            {"m": "M5", "k": "expense_committed", "s": "banners", "v": 8000, "st": "confirmed", "c": 1.0},
        ]
    }


def extract_mock_result(user_prompt: str) -> str:
    """Extracts claims for mock provider based on prompt content."""
    # Check known packs anywhere in the prompt
    prompt_lower = user_prompt.lower()
    if "96 students" in prompt_lower or "skyline convention" in prompt_lower:
        return json.dumps(_pack1_data())
    if "132 participants" in prompt_lower or "centaurus expo" in prompt_lower or "build-a-thon" in prompt_lower:
        return json.dumps(_pack2_data())
    if "120 students" in prompt_lower or "city banquets" in prompt_lower or "vegetarian" in prompt_lower:
        return json.dumps(_pack3_data())
    if "72 students" in prompt_lower or "hotel serena" in prompt_lower:
        return json.dumps(_pack4_data())

    # Extract ONLY the target message text (ignore KNOWN FACTS and prompt template)
    msg_part = user_prompt
    if "NEW MESSAGE(S) - extract only from these:" in user_prompt:
        msg_part = user_prompt.split("NEW MESSAGE(S) - extract only from these:")[-1]
    elif "MESSAGES:" in user_prompt:
        msg_part = user_prompt.split("MESSAGES:")[-1]

    # Find message ID (e.g. M11 | text)
    m_match = re.search(r"(M\d+)\s*\|\s*(.*)", msg_part, re.DOTALL)
    if m_match:
        target_id = m_match.group(1)
        raw_text = m_match.group(2).strip()
    else:
        target_id = "M1"
        raw_text = msg_part.strip()

    text_lower = raw_text.lower()
    claims = []
    
    # Infer authority and sender
    auth = 2
    sender = "Update"
    if "accounts" in text_lower or "registrar" in text_lower or "admin" in text_lower or "office" in text_lower:
        auth = 3
        sender = "Authority"
    elif "volunteer" in text_lower or "club" in text_lower or "student" in text_lower:
        auth = 1
        sender = "Participant"

    messages = [{"id": target_id, "sender": sender, "date": "2026-11-18", "auth": auth, "relevant": True}]

    # 1. Committed expense (e.g. "banners invoice is 9000, not 5000" or "trophies bill 40000")
    exp_match = re.search(r"(\b\w+\b)\s+(?:invoice|bill|cost|fee|expense)\s+(?:is|was|of)?\s*(?:rs\.?|pkr)?\s*([0-9,]+)", text_lower)
    if exp_match:
        item = exp_match.group(1)
        val = int(exp_match.group(2).replace(",", ""))
        claims.append({"m": target_id, "k": "expense_committed", "s": item, "v": val, "st": "corrected", "c": 1.0})

    # 2. Proposed quote (e.g. "fireworks quote 20000" or "photographer quote 25k")
    prop_match = re.search(r"(\b\w+\b)\s+quote\s+(?:rs\.?|pkr)?\s*([0-9,]+)(k)?", text_lower)
    if prop_match:
        item = prop_match.group(1)
        val = int(prop_match.group(2).replace(",", "")) * (1000 if prop_match.group(3) else 1)
        claims.append({"m": target_id, "k": "expense_proposed", "s": item, "v": val, "st": "proposed", "c": 0.8})

    # 3. Food quantity / boxes (e.g. "rounded down to 30 boxes")
    boxes_match = re.search(r"(\d+)\s+boxes", text_lower)
    if boxes_match:
        qty = int(boxes_match.group(1))
        claims.append({"m": target_id, "k": "food_order_quantity", "v": qty, "st": "proposed", "c": 0.8})

    # 4. Food price (e.g. "wrap meal is now Rs 800" or "biryani box ab 1050")
    food_match = re.search(r"([a-z\s]+?)\s+(?:is\s+now|ab|price|rate)\s+(?:rs\.?|rupay)?\s*([0-9,]+)", text_lower)
    if food_match and not exp_match and not prop_match:
        item = food_match.group(1).replace("caterer", "").replace("cook", "").strip()
        val = int(food_match.group(2).replace(",", ""))
        claims.append({"m": target_id, "k": "food_price_per_head", "s": item, "v": val, "st": "corrected", "c": 1.0})

    # 5. Students / participants
    stu_match = re.search(r"(\d+)\s+(?:students|participants)", text_lower)
    if stu_match:
        claims.append({"m": target_id, "k": "students", "v": int(stu_match.group(1)), "st": "confirmed", "c": 1.0})

    # 6. Judges
    judge_match = re.search(r"(\d+)\s+(?:judges|jurors)", text_lower)
    if judge_match:
        claims.append({"m": target_id, "k": "judges_available", "v": int(judge_match.group(1)), "st": "confirmed", "c": 1.0})

    # 7. Irrelevant chatter
    if "cricket" in text_lower or "match" in text_lower or "parking" in text_lower or "party" in text_lower:
        messages[0]["relevant"] = False
        messages[0]["why"] = "irrelevant message"
        claims = []

    return json.dumps({"messages": messages, "claims": claims})
