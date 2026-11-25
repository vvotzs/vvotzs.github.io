import json

p = "data/deals_en.json"
en = json.load(open(p))

en["eskimo-free-esim"] = {
 "title": "[Global] Eskimo free eSIM: 250MB of global data for new users (126 countries, no expiry)",
 "highlight": "Enter FREE250MB as the referral or gift code at signup for 250MB of free global data covering 126 countries and regions, with no expiry and no credit card",
 "regions": "[Global] 126+ countries including Japan, China, the US, Italy and Thailand; new users only",
 "value": "250MB (about $2)",
 "content": "A free trial from travel eSIM brand Eskimo (Singapore's Datapro): new users enter FREE250MB in the referral or gift code field when registering in the app for 250MB of global data across 126+ countries. The page says no card is needed, one install covers many countries and the data never expires, suiting maps, rides and messages on arrival. When rechecked on 2026-11-26 the official page kept only the 250MB tier (the older 500MB FREE500MB code is gone from it, though some older accounts still work); see the separate entry for the larger 1GB gift code.",
 "conditions": "New Eskimo users only; enter the code at signup in the app, or within 24 hours after; once per account; data never expires, though accounts unused for about two years are closed; mainland-China phones without native eSIM need a QR code from support for a writable card (APN Singtel Postpaid, do not delete after installing).",
 "steps": [
  "Download the Eskimo app (developer Datapro Technologies)",
  "Register a new account with email or Google and enter FREE250MB as the referral or gift code",
  "Check the Data page for the Global 250MB plan",
  "Install directly on an eSIM-capable phone, or ask support for the QR code to write to a blank card on a mainland-China handset",
  "On arrival set mobile data to that eSIM and turn on data roaming"
 ],
 "risk": "250MB is only enough for emergencies (a few hours of maps and messages) with no calls; the official tier has dropped from 500MB to 250MB, so check the amount shown in the app after entering the code; mainland-China phones need an extra blank eUICC card, and a failed write has to be redone.",
 "source": "Eskimo official free eSIM page (eskimo.travel/en/free-esim, rechecked 2026-11-26: FREE250MB / 250MB / 126 countries / no expiry)"
}

en["eskimo-gift-1gb-code"] = {
 "title": "[Global] Eskimo gift code ESIMKART1GB: 1GB global eSIM for new users (valid 2 years, to 11/30)",
 "highlight": "Enter the gift code ESIMKART1GB at signup and a new account gets 1GB of global data (about $7) with no plan to buy and no card",
 "regions": "[Global] 120+ countries and regions (a few, such as Singapore, are excluded); new users only",
 "value": "1GB (about $7)",
 "content": "A limited new-user gift code from Eskimo: a new account enters ESIMKART1GB on the app signup screen (or in the Vouchers/Gifts page within 24 hours) and 1GB of global data lands in the account, with nothing to pay and no card. Eskimo's partner Triple-A said in a 2026-08-19 announcement that new users get a complimentary 1GB global eSIM worth $7 until 2026-11-30; the code page at eSIMKart dates the code to 2027-09-09 but caps total redemptions, so it can close early. A Cheapies NZ user reported on 2026-11-25 that signing up with just a name and email and entering the code in the app credited the data, valid about two years.",
 "conditions": "New Eskimo users only; enter the code at app signup (existing accounts can add it on the Vouchers/Gifts page), once per account; the phone must support eSIM and be network unlocked; the covered countries are those listed in the app (Singapore is not included); the official campaign runs to 2026-11-30 and total redemptions are capped.",
 "steps": [
  "Download the Eskimo app (developer Datapro Technologies) and register a new account with an email",
  "Enter ESIMKART1GB in the referral/gift code field at signup, or on the Vouchers/Gifts page within 24 hours",
  "Check the Data page for a 1GB Global plan",
  "Install it on an eSIM-capable phone, or ask support for a QR code to write to a blank card on a mainland-China handset",
  "On arrival set mobile data to that eSIM and turn on data roaming"
 ],
 "risk": "The 1GB is a one-off gift with no calls; total redemptions are capped so the code can stop working early; some countries (Singapore among them) are not covered; an eSIM-capable unlocked phone is required, and mainland-China handsets need a writable card.",
 "source": "Triple-A official partner announcement (2026-08-19: free 1GB global eSIM worth $7 for new users, to 2026-11-30) + eSIMKart gift-code page (ESIMKART1GB, listed to 2027-09-09 with a redemption cap) + Cheapies NZ hands-on post 2026-11-25 (node/57972)"
}

en["elevenlabs-startup-grants"] = {
 "title": "[Global] ElevenLabs startup grants: 12 months of Scale + 33M characters (worth $5,500+, rolling)",
 "highlight": "Approved early-stage startups get 12 months of Scale plus 33 million characters (ElevenLabs puts the value above $5,500) covering TTS, voice cloning and Agents, usually with a decision within a week",
 "regions": "[Global] Apply online; startups and small companies with fewer than 25 employees only (agencies, consultancies and SMBs don't qualify)",
 "value": "$5,500+ (12 months Scale + 33M characters)",
 "content": "ElevenLabs Grants targets early-stage startups: an approved team gets 12 months of the Scale plan plus 33 million characters (ElevenLabs equates that to over 680 hours of Agents usage, worth more than $5,500), along with founder community events and support. It asks for a clear monetization path and a company email, and does not fund one-off projects, campaigns or products for anyone under 18; companies must have fewer than 25 employees, and agencies, consultancies and SMBs are excluded; one application per company, paying self-serve customers can apply but enterprise customers cannot. Applications roll and usually get an answer within a week; the plan falls back to Free when the characters run out or after 12 months.",
 "conditions": "A company email and a clear monetization plan are required; startups or small companies with fewer than 25 employees; one-off projects, agencies, consultancies and products for minors are not accepted; one application per company; credits cannot be resold; the plan reverts to Free at 12 months or when the 33M characters are used.",
 "steps": [
  "Open elevenlabs.io/startup-grants and click Apply to describe the company, product and growth plan",
  "Submit with a company email and wait about a week for the review",
  "Once approved, the credits are applied to the account you applied with",
  "Confirm the Scale plan and 33M characters are active in the dashboard before integrating the API"
 ],
 "risk": "This is an application-based grant, not something everyone can claim, and mismatched products or teams are refused; credits cannot be resold, and the account drops back to Free when they run out or the year ends, so plan the renewal before shipping.",
 "source": "ElevenLabs official Grants page (rechecked 2026-11-26: 12 months Scale, 33,000,000 characters, $5,500+ value, answer within a week, fewer than 25 employees)"
}

with open(p, "w") as f:
    json.dump(en, f, ensure_ascii=False, indent=1)
    f.write("\n")
print("ok en:", len(en))
