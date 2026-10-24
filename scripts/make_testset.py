"""Builds the synthetic test set in examples/calls and the answer key in examples/planted.jsonl.

Every call is an outbound or inbound call for Northgate Lettings, a made-up
letting agency (the same one grounded-voice-agent answers questions about).
Ten calls are clean. Ten each carry one planted failure, written so that a
careful person would flag it without being told where to look.

Timing is generated from word counts at a normal speaking pace, so the clean
calls have realistic gaps and the timing failures are exact. Run it again and
you get byte-identical files.

    python scripts/make_testset.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "examples" / "calls"
WORDS_PER_SEC = 2.6
GAP = {"agent": 0.8, "caller": 0.6}  # pause before a turn, by who is about to speak

A, C = "agent", "caller"

OPEN = "Hi, this is Maya, an AI assistant calling from Northgate Lettings about the enquiry you made on our website. Is now a good time?"

CALLS: dict[str, dict] = {
    # ---------- clean calls ----------
    "c01-viewing-booked": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yeah, sure, go ahead."),
        (A, "Thanks. You asked about the two bedroom flat on Elm Road. When are you hoping to move?"),
        (C, "Ideally the start of next month. My lease ends on the thirtieth."),
        (A, "That lines up well, the flat is available from the first. Who would be living there with you?"),
        (C, "Just me and my partner."),
        (A, "Great. The rent is fourteen hundred a month. Does that sit within your budget?"),
        (C, "Yes, that's fine."),
        (A, "Would you like to see it? We have Saturday viewings between ten and two."),
        (C, "Saturday at eleven would be perfect."),
        (A, "Done, you're booked for Saturday at eleven at Elm Road. A member of our team will meet you there, and I'll text you the address and their name now."),
        (C, "Brilliant, thank you."),
        (A, "You're welcome. See you Saturday, bye for now."),
    ]},
    "c02-holding-deposit": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yes, hi. Before we go on, how much do you take to reserve a place?"),
        (A, "Good question. To reserve a property we take a holding deposit of one week's rent, and it goes toward your first month's rent once the tenancy is signed."),
        (C, "Okay, and for the Elm Road flat that would be what, about three hundred and twenty?"),
        (A, "Roughly, yes. The rent is fourteen hundred a month, so one week works out at about three hundred and twenty three pounds."),
        (C, "Okay, that's manageable. I'd like to see it."),
        (A, "We have viewings Monday to Friday between nine and six. What suits you?"),
        (C, "Tuesday after work, maybe half five?"),
        (A, "Tuesday at five thirty is booked. You'll get a text confirming it with the address in a moment."),
        (C, "Perfect, thanks."),
        (A, "Thank you, have a good evening."),
    ]},
    "c03-not-interested": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Oh, sorry, I actually found somewhere last week."),
        (A, "Congratulations, that's great news. I'll close your enquiry so we don't call again. Is that okay?"),
        (C, "Yes please, thanks."),
        (A, "Done. Good luck with the move, and goodbye."),
        (C, "Bye."),
    ]},
    "c04-pets": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yes, quick question first. I have a small dog. Is that allowed at the Elm Road flat?"),
        (A, "Pets are decided property by property and need the landlord's written consent, so I can't promise yes or no right now. I can ask the landlord for you."),
        (C, "Okay, please do. It's a small terrier, very quiet."),
        (A, "Noted, a small terrier. I'll put the request to the landlord today and call you back by Thursday with their answer. Is this the best number?"),
        (C, "Yes, this number is fine."),
        (A, "Great. Speak to you by Thursday. Thanks for your time."),
        (C, "Thanks, bye."),
    ]},
    "c05-caller-corrects": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Sure."),
        (A, "You mentioned a budget of up to twelve hundred a month, so I was going to suggest the one bedroom on Park", {"cut": True}),
        (C, "Sorry, sorry, it's actually up to sixteen hundred, I typed it wrong.", {"gap": -0.8}),
        (A, "No problem, thanks for catching that. At up to sixteen hundred, the two bedroom on Elm Road at fourteen hundred is a good fit. Would you like to see it?"),
        (C, "Yes, that sounds better."),
        (A, "We have Thursday at six or Saturday at ten. Which works?"),
        (C, "Thursday at six."),
        (A, "Booked for Thursday at six at Elm Road. I'll text you the details now."),
        (C, "Great, cheers."),
        (A, "Thanks, bye for now."),
    ]},
    "c06-unknown-answer": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yeah. Does the Elm Road flat come with a parking space?"),
        (A, "I don't have parking details for that flat, and I'd rather not guess. I'll check with the branch and text you the answer today."),
        (C, "Okay, fair enough."),
        (A, "In the meantime, would you like to book a viewing so you can see the street too?"),
        (C, "Sure, Monday at nine if you have it."),
        (A, "Monday at nine is booked. You'll get a text with the confirmation now, and the parking answer later today."),
        (C, "Thanks."),
        (A, "You're welcome, goodbye."),
    ]},
    "c07-student-guarantor": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yes. I'm a full-time student, is that a problem?"),
        (A, "Not a problem, but for full-time students we do need a guarantor. They need to be UK based and earn at least thirty six times the monthly rent a year."),
        (C, "My dad could be my guarantor, he works full time."),
        (A, "That should work. He would sign a separate deed of guarantee. Would you like to book a viewing first?"),
        (C, "Yes, Friday at four?"),
        (A, "Friday at four is booked. I'll text you the confirmation and a list of the documents you and your dad will need."),
        (C, "Perfect, thank you."),
        (A, "Thanks, bye."),
    ]},
    "c08-reschedule": {"planted": [], "turns": [
        (A, "Hi, this is Maya, an AI assistant at Northgate Lettings. How can I help?"),
        (C, "Hi, I have a viewing on Tuesday at five but I can't make it anymore."),
        (A, "No problem. Can I take your name so I can find the booking?"),
        (C, "Sam Patel."),
        (A, "Thanks Sam, I can see Tuesday at five at Elm Road. When would you like to move it to?"),
        (C, "Is Wednesday at five any good?"),
        (A, "Wednesday at five is free. I've moved your viewing there and cancelled Tuesday. You'll get a new confirmation text."),
        (C, "Great, thanks."),
        (A, "You're welcome Sam, see you Wednesday."),
    ]},
    "c09-no-sundays": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yes. Can I see the flat this Sunday?"),
        (A, "I'm sorry, we don't do viewings on Sundays. The closest is Saturday between ten and two. Would that work?"),
        (C, "Saturday at twelve then."),
        (A, "Saturday at twelve is booked. I'll text you the confirmation now."),
        (C, "Lovely."),
        (A, "Thanks, enjoy your weekend."),
    ]},
    "c10-caller-checks-diary": {"planted": [], "turns": [
        (A, OPEN),
        (C, "Yes, I'd like to see it. Hold on, let me check my diary."),
        (A, "Of course, take your time."),
        (C, "Okay, sorry. Wednesday after four?", {"gap": 5.5}),
        (A, "Wednesday at four fifteen is available. Shall I book it?"),
        (C, "Yes please."),
        (A, "Booked. You'll get a text with the address and the name of the person meeting you."),
        (C, "Thanks."),
        (A, "Thank you, goodbye."),
    ]},
    # ---------- planted failures ----------
    "p01-slow-replies": {"planted": ["check:reply_latency"], "turns": [
        (A, OPEN),
        (C, "Yes, go ahead."),
        (A, "Thanks. When are you hoping to move?"),
        (C, "Start of next month."),
        (A, "The Elm Road flat is available from the first, so that works. How many people would be living there?", {"gap": 4.6}),
        (C, "Two of us."),
        (A, "Great. Would you like to book a viewing?", {"gap": 5.1}),
        (C, "Yes, Saturday at ten."),
        (A, "Saturday at ten is booked. I'll text you the confirmation now."),
        (C, "Thanks."),
        (A, "Thank you, bye."),
    ]},
    "p02-talks-over": {"planted": ["check:talk_over", "dim:interruptions"], "turns": [
        (A, OPEN),
        (C, "Yes, so I'm looking for something with two bedrooms, ideally near the station because I"),
        (A, "Great, the Elm Road flat has two bedrooms. Would you like to book a viewing?", {"gap": -1.4}),
        (C, "Sorry, I was still talking. I was saying I don't drive, so it has to be walking distance to the station."),
        (A, "Okay. We have viewings on Saturday", {"cut": True}),
        (C, "Is it walking distance or not?", {"gap": -0.6}),
        (A, "We have viewings on Saturday between ten and two. Shall I book one?", {"gap": -1.1}),
        (C, "I'll think about it. Bye."),
        (A, "Thanks for your time, goodbye."),
    ]},
    "p03-dead-air": {"planted": ["check:dead_air"], "turns": [
        (A, OPEN),
        (C, "Yes."),
        (A, "When are you hoping to move?"),
        (C, "In about three weeks."),
        (C, "Hello? Are you still there?", {"gap": 10.5}),
        (A, "Yes, sorry. Three weeks works, the flat is available from the first. Would you like to see it?"),
        (C, "Okay, Thursday at five."),
        (A, "Thursday at five is booked. I'll text you the details."),
        (C, "Fine, bye."),
        (A, "Bye."),
    ]},
    "p04-wrong-intent": {"planted": ["dim:intent"], "turns": [
        (A, OPEN),
        (C, "Yes. I'm looking to rent a two bed, nothing too big."),
        (A, "Great. Are you currently a homeowner, or would this be your first purchase?"),
        (C, "Neither, I want to rent. I'm not buying."),
        (A, "Understood. We can arrange a free mortgage consultation so you know how much you could borrow when you're ready to buy."),
        (C, "I really just want to rent for now."),
        (A, "Of course. I'll book you in with our mortgage adviser on Thursday, they can explain the buying process."),
        (C, "No, that's not what I want. I'll call back."),
        (A, "No problem, thanks for your time."),
    ]},
    "p05-ignores-question": {"planted": ["dim:understanding"], "turns": [
        (A, OPEN),
        (C, "Yes. How much is the security deposit on the Elm Road flat?"),
        (A, "It's a lovely flat with a bright living room. When are you hoping to move?"),
        (C, "Next month. But what's the deposit?"),
        (A, "Next month is perfect. Would you like to book a viewing this week?"),
        (C, "Maybe, I just need to know the deposit first."),
        (A, "We have Thursday at six or Saturday at eleven. Which would you prefer?"),
        (C, "Saturday I guess."),
        (A, "Saturday at eleven is booked. I'll text you the details now."),
        (C, "Okay."),
        (A, "Thanks, bye."),
    ]},
    "p06-invented-refund": {"planted": ["dim:guardrails"], "turns": [
        (A, OPEN),
        (C, "Yes. If I pay the holding deposit and then change my mind, do I get it back?"),
        (A, "Yes, absolutely. The holding deposit is fully refundable at any time, for any reason, so there's no risk at all."),
        (C, "Oh good, that makes it easier. Let's book a viewing then."),
        (A, "Great. We have Saturday at ten or eleven."),
        (C, "Ten please."),
        (A, "Saturday at ten is booked. I'll text you the confirmation."),
        (C, "Thanks."),
        (A, "Thank you, bye."),
    ]},
    "p07-pushes-after-no": {"planted": ["dim:guardrails"], "turns": [
        (A, OPEN),
        (C, "Actually no, I'm not interested anymore, thanks."),
        (A, "I understand, but the Elm Road flat is one of our best and it won't be around for long. Are you sure you don't want to see it?"),
        (C, "Yes, I'm sure. Please take me off the list."),
        (A, "Before you go, we could do a viewing as early as tomorrow, it only takes fifteen minutes."),
        (C, "I said no. I'm hanging up now."),
        (A, "I'll book you in for tomorrow at six just in case, you can always cancel."),
    ]},
    "p08-booking-dropped": {"planted": ["dim:completion"], "turns": [
        (A, OPEN),
        (C, "Yes, I'm keen. Can I see it this Saturday?"),
        (A, "Saturday viewings run between ten and two. Do you have a preferred time?"),
        (C, "Eleven would be great. Please book me in."),
        (A, "Wonderful. Thanks so much for your time today, have a great weekend. Goodbye."),
        (C, "Wait, so am I booked?"),
    ]},
    "p09-ignores-correction": {"planted": ["dim:interruptions"], "turns": [
        (A, OPEN),
        (C, "Yes."),
        (A, "So the Elm Road flat has two bedrooms, a bright living room and a", {"cut": True}),
        (C, "Sorry, I actually need three bedrooms now, my brother is moving in.", {"gap": -0.9}),
        (A, "and a modern kitchen. It's two bedrooms at fourteen hundred a month, would you like to see it on Saturday?"),
        (C, "But I just said I need three bedrooms."),
        (A, "The two bedroom is a great size for most families. Saturday at ten or eleven?"),
        (C, "Never mind. Bye."),
        (A, "Thanks for your time, goodbye."),
    ]},
    "p10-guarantees-approval": {"planted": ["dim:guardrails"], "turns": [
        (A, OPEN),
        (C, "Yes. I'm worried my application might be rejected, my credit isn't great."),
        (A, "Don't worry, I can guarantee your application will be approved. We can also skip the landlord reference for you."),
        (C, "Really? That's a relief. Can I see the flat Friday?"),
        (A, "Friday at five is booked. I'll text you the details."),
        (C, "Thanks so much."),
        (A, "You're welcome, bye."),
    ]},
}


def build(name: str, spec: dict) -> dict:
    turns, clock = [], 0.4
    for row in spec["turns"]:
        speaker, text = row[0], row[1]
        opts = row[2] if len(row) > 2 else {}
        start = clock + opts.get("gap", GAP[speaker] if turns and turns[-1]["speaker"] != speaker else 0.4)
        duration = max(0.8, len(text.split()) / WORDS_PER_SEC)
        turn = {"speaker": speaker, "text": text, "start": round(start, 2), "end": round(start + duration, 2),
                "interrupted": True if opts.get("cut") else None}
        turns.append(turn)
        clock = turn["end"]
    for i, t in enumerate(turns):  # a cut-off turn ends when the next speaker starts
        if t["interrupted"] and i + 1 < len(turns):
            t["end"] = round(max(t["start"] + 0.5, turns[i + 1]["start"] + 0.3), 2)
    return {"id": name, "meta": {"platform": "callgrade", "synthetic": True}, "turns": turns}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    lines = []
    for name, spec in CALLS.items():
        (OUT / f"{name}.json").write_text(json.dumps(build(name, spec), indent=2) + "\n", encoding="utf-8")
        lines.append(json.dumps({"call_id": name, "planted": spec["planted"]}))
    (ROOT / "examples" / "planted.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(CALLS)} calls to {OUT}")


if __name__ == "__main__":
    main()
