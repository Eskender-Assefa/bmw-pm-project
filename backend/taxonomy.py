import re
import hashlib
from .models import Category, Feature, Vehicle

CATEGORIES = {
    'C01': 'Power & Performance', 'C02': 'Energy & Emissions', 'C03': 'Price',
    'C04': 'Safety', 'C05': 'Comfort', 'C06': 'Exterior', 'C07': 'Software',
    'C08': 'Interior Design', 'C09': 'Automation', 'C10': 'Miscellaneous',
}

# Explicit source-tag ownership, rather than a language model's changing taxonomy.
TAG_GROUPS = {
 'C01': '''Drive, driving dynamics and chassis, overall technology|Drivetrain|Transmission|Operate selector lever|Shift paddle|Launch Control|Starting engine|Start engine/switch on drive readiness|Automatic engine start-stop function (MSA)|Engine oil|Exhaust system''',
 'C02': '''Electric Range|Charge high-voltage battery|High voltage battery|High voltage battery, preconditioning|Bidirectional charging|Charging cable|High-voltage charging power socket|Opening/closing charging socket cover|Public charging / external providers|Wallbox, charging / home charging|Route optimized for charging|Brake Energy Regeneration / recuperation|Fuel tank|Fuel filler flap , open / close''',
 'C04': '''Braking|Parking brake|Automatic-hold|Steering|Steering wheel|Cushioning / damping vehicle|Self-leveling suspension|Handling / Riding|Airbags|Seat belts|Child restraint seat|Child restraint seat, use|Child safety latch|Dynamic Stability Control|Dynamic Stability Control (DSC)|Vehicle safety, overall technology|Impression of safety|Tire pressure control|RSC tire|Wheels / tires|Tirefit|Emergency request|Pedals, operate|Horns''',
 'C05': '''Interior comfort|Interior acoustics|Seats|Headrest, adjust|Headrests, rear|Adjustment of lower lumbar support|Seating, ventilate / heat|Seat massage|Seat memory|Air conditioning control panel|Air conditioning, overall technology|Air conditioning, setting|Vehicle, climatization|Cooling|Blower function|Auxiliary heater function|Panel heating|Heated steering wheel|Heated rear window|Audio mode, sound|Radio function|CD / DVD changer, playback|Rear seat entertainment|Vehicle, access and exit|Comfort Access|Vehicle key|Digital Key|Display key|Vehicle, lock / unlock|Door, open / close|Automatic doors|Trunk lid, open / close|non-contact trunk lid opening|Mobile device, wireless charging|USB port|12 V connection|Vehicle battery|Remote Engine Start (My BMW App / MINI App)|Remote Engine Start (Vehicle Key )|Remote Services & Remote Keyless Entry (My BMW App/MINI App)|Sun protection|Sun visor, front|Garage door opener|Interior mirror, garage door opener|Resting state after door opening|Engine acoustics / engine sound''',
 'C06': '''Exterior|Exterior design|Exterior lighting|Light switch operating unit|Flashing|Fog light|Welcome Light Carpet|Windshield|Exterior rearview mirror|Panorama glass roof|Roof|Opening / closing convertible top / hardtop|Side window, open / close|Outer door handle, front|Outer door handle, rear|Radiator grille|Bumper, front|Bumper, rear|Door, front|Hood|Hood, open / close|Trunk lid|Running board|Side sill trim panel|Roof function centre''',
 'C07': '''ConnectedDrive and Infotainment, overall technology|ConnectedDrive services (smartphone) technology overall|Operating concept, operating system|Touch screen, operation|Controller operation|Multi-function steering wheel operation|Touch Command|Gesture control|Voice control / speech recognition|Intelligent Personal Assistant|Intelligent Personal Assistant, activation word|Instrument cluster|Head-Up Display|Display, time|Driver profile|Experience Modes|My Modes / driving experience|Caring Car|Navigation|Map update|Smart POI search|Real Time Traffic Information (RTTI)|Traffic Camera Information|Apple CarPlay|Android Auto|Manage / pair mobile device (Bluetooth)|Priorities for telephones|Screen mirroring|Wi-Fi connection|WiFi hotspot|Personal eSIM|Apps (in-car)|Apps (smartphone)|BMW Online / MINI Online|BMW ConnectedDrive upgrades/ MINI CONNECTED upgrades|My BMW App / MINI App|Customer Account (My BMW / MINI Portal)|My BMW / MINI Portal|Remote Software Upgrade/RSU|Video: playback / streaming|Driver's Guide App''',
 'C08': '''Interior|Interior design|Upholstery / interior trim|Ambient light|Vehicle interior, lighting|Instrument panel|Center console, front|Center armrest, front|Door, finisher panel, front|Space / spatial impression|Floor mat|Grab handle''',
 'C09': '''(Active) cruise control|Back-up Assistant|Blind spot monitoring|Cross Traffic Warning Rear with Brake Intervention|Drive Recorder|Driver assistance, automated driving, overall technology|Emergency Stop Assistant|Fatigue Alert|Front collision warning|High-beam assistant|Highway assistant|Interior camera|Intersection Warning with Brake Intervention|Lane Change Assistant|Lane departure warning|Night Vision|Park Distance Control (PDC)|Parking Assistant|Rear view camera|Rear-end collision warning|Remote 3D View (My BMW App / MINI App)|Remote controlled parking|Remote interior camera (My BMW App / MINI App)|Side View|Speed Limit Assistant|Steering and lane guide assist|Surround View|Traffic Jam Assistant|Traffic Light And Sign Warning''',
 'C10': '''Owner's Manual|Luggage compartment|Frunk|Storage compartments|Cupholder|Glove box|Through-loading facility|Trailer, use|Towing eye|Teleservices|Accessories / Parts|General enquiry: customer feedback|Body equipment, overall technology|Anti-theft alarm system|All-round view|Interior rearview mirror|Rain sensor mode|Rear wiper|Wash / wipe switch|Washer fluid, top up|Windshield wiper|Trunk light''',
}
TAG_MAP = {tag.casefold(): cat for cat, tags in TAG_GROUPS.items() for tag in tags.split('|')}

def feature_slug(tag):
    return re.sub(r'[^a-z0-9]+', '-', tag.casefold()).strip('-')[:95]

def feature_for_tag(session, tag):
    tag = tag.strip() if tag and tag != 'no_class_found' else 'Unclassified feedback'
    feature_id = feature_slug(tag)
    feature = session.get(Feature, feature_id)
    if feature:
        return feature
    category = TAG_MAP.get(tag.casefold(), 'C10')
    mapped = tag.casefold() in TAG_MAP
    feature = Feature(id=feature_id, name=tag, category=category,
        secondary_tags=['Comfort', 'Performance'] if 'suspension' in tag.casefold() or 'damping' in tag.casefold() else [],
        mapping_reason='Explicit source-tag dictionary; semantic match still needs review.' if mapped else 'other_pending_review: no dictionary match; owner Demo PM.')
    session.add(feature)
    session.flush()
    return feature

def seed_taxonomy(session):
    for key, name in CATEGORIES.items():
        if not session.get(Category, key):
            session.add(Category(id=key, name=name))
    for code, name in [('F70','1 Series'), ('G60','5 Series'), ('G68','5 Series long wheelbase'), ('G70','7 Series'), ('G60_G68','5 Series combined sales family')]:
        if not session.get(Vehicle, code):
            session.add(Vehicle(id=code, model=code, name=name, aliases=[code]))
    session.flush()

def serious_concern(text, kind):
    if kind == 'Likes':
        return False
    return bool(re.search(r'brak(?:e|es|ing).{0,45}(?:fail|did not|not work|stopped working)|(?:unintended|uncommanded|sudden) acceleration|airbag.{0,35}(?:fail|deploy)|lost (?:steering|control)|vehicle.{0,25}caught fire', text, re.I))
