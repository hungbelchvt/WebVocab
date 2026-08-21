"""
Database Seeding System for WebVocab.
Populates PostgreSQL / SQLite database with 15 comprehensive vocabulary topics
and over 500 rich English vocabulary items with IPA, definitions, examples,
synonyms, antonyms, and difficulty ratings.

Idempotent and safe to run multiple times without duplicating data.
Usage:
    python seed.py
"""

import sys
from datetime import datetime, timezone, timedelta
import random
from werkzeug.security import generate_password_hash
from sqlalchemy import func

from app import create_app
from app.models import db, User, Topic, Word, WordProgress

# =====================================================================
# Seed Data Definitions: 15 Topics x 35 Words = 525 Vocabulary Items
# =====================================================================

VOCAB_DATA = {
    "Daily Life": [
        ("Routine", "ruːˈtiːn", "A sequence of actions regularly followed.", "Her morning routine includes meditation and coffee.", "habit, schedule", "disorder", "easy"),
        ("Chore", "tʃɔːr", "A routine task, especially a household one.", "Doing the dishes is my least favorite household chore.", "duty, task", "leisure", "easy"),
        ("Commute", "kəˈmjuːt", "A regular journey of some distance to and from one's place of work.", "His daily commute takes forty-five minutes by train.", "travel, journey", "stay", "medium"),
        ("Leisure", "ˈliːʒər", "Free time spent away from business or work.", "Reading novels is her favorite leisure activity.", "free time, relaxation", "labor, work", "easy"),
        ("Errand", "ˈerənd", "A short journey undertaken in order to deliver or collect something.", "I have to run a few errands at the post office today.", "task, mission", "", "medium"),
        ("Punctual", "ˈpʌŋktʃuəl", "Happening or doing something at the agreed or proper time.", "She is always punctual for her morning meetings.", "on time, prompt", "late, tardy", "medium"),
        ("Appliance", "əˈplaɪəns", "A device or piece of equipment designed to perform a specific domestic task.", "The kitchen is equipped with modern stainless steel appliances.", "device, machine", "", "easy"),
        ("Groceries", "ˈɡroʊsəriz", "Items of food and other goods sold in a food store.", "We buy fresh groceries at the neighborhood supermarket every Saturday.", "provisions, food", "", "easy"),
        ("Tidy", "ˈtaɪdi", "Arranged neatly and in order.", "Please keep your desk tidy before leaving the office.", "neat, orderly", "messy, untidy", "easy"),
        ("Habit", "ˈhæbɪt", "A settled or regular tendency or practice.", "Drinking water first thing in the morning is a healthy habit.", "custom, pattern", "", "easy"),
        ("Multitask", "ˌmʌltiˈtæsk", "Deal with more than one task at the same time.", "Listening to a podcast while folding laundry is easy to multitask.", "juggle", "focus", "medium"),
        ("Hygiene", "ˈhaɪdʒiːn", "Conditions or practices conducive to maintaining health and preventing disease.", "Good dental hygiene prevents cavities and gum issues.", "cleanliness, sanitation", "filth", "medium"),
        ("Fatigue", "fəˈtiːɡ", "Extreme tiredness resulting from mental or physical exertion or illness.", "After working sixty hours this week, he suffered from severe fatigue.", "exhaustion, weariness", "energy, vigor", "hard"),
        ("Hydrate", "ˈhaɪdreɪt", "Cause to absorb water or other liquid.", "Remember to hydrate frequently when exercising in hot weather.", "drink, moisturize", "dehydrate", "easy"),
        ("Alarm", "əˈlɑːrm", "A signal or device warning of danger or waking someone up.", "My alarm rings at six o'clock every morning.", "alert, siren", "", "easy"),
        ("Laundry", "ˈlɔːndri", "Clothes and linen that need to be washed or that have been newly washed.", "I need to fold the clean laundry this evening.", "washing", "", "easy"),
        ("Balcony", "ˈbælkəni", "A platform enclosing a space outside a building.", "We enjoyed having breakfast on the sunny balcony.", "terrace, patio", "", "easy"),
        ("Wardrobe", "ˈwɔːrdroʊb", "A large, tall cupboard in which clothes may be hung or stored.", "She organized her winter coats inside the wooden wardrobe.", "closet, armoire", "", "easy"),
        ("Neighborhood", "ˈneɪbərhʊd", "A district or community within a town or city.", "The neighborhood is peaceful with tree-lined sidewalks.", "district, community", "", "easy"),
        ("Pantry", "ˈpæntri", "A small room or cupboard in which food, crockery, and utensils are kept.", "We stocked the pantry with canned beans and rice.", "larder, storeroom", "", "easy"),
        ("Dwell", "dwel", "Live in or at a specified place.", "Many artisans dwell in this historic district.", "reside, inhabit", "leave, vacate", "medium"),
        ("Cuisine", "kwɪˈziːn", "A style or method of cooking, especially characteristic of a particular country or region.", "Italian cuisine is world-renowned for fresh pasta.", "cooking, food", "", "medium"),
        ("Neighbor", "ˈneɪbər", "A person living near or next door to another.", "Our neighbor kindly watered our houseplants while we were away.", "fellow resident", "stranger", "easy"),
        ("Declutter", "ˌdiːˈklʌtər", "Remove unnecessary items from an untidy or overcrowded place.", "Spring is the best time to declutter the basement.", "organize, tidy", "clutter, mess", "medium"),
        ("Indulge", "ɪnˈdʌldʒ", "Allow oneself to enjoy the pleasure of.", "On weekends, I like to indulge in a slice of dark chocolate cake.", "treat, pamper", "abstain, deny", "hard"),
        ("Frugal", "ˈfruːɡəl", "Sparing or economical with regard to money or food.", "By leading a frugal lifestyle, she saved enough for a house down payment.", "thrifty, economical", "wasteful, lavish", "hard"),
        ("Cozy", "ˈkoʊzi", "Giving a feeling of comfort, warmth, and relaxation.", "The small living room felt cozy with a crackling fireplace.", "snug, comfortable", "uncomfortable, cold", "easy"),
        ("Sedentary", "ˈsednteri", "Tending to spend much time seated; somewhat inactive.", "A sedentary office job requires regular exercise breaks.", "inactive, desk-bound", "active, dynamic", "hard"),
        ("Stroll", "stroʊl", "Walk in a leisurely way.", "We took an evening stroll along the riverbank.", "walk, wander", "run, sprint", "easy"),
        ("Simplicity", "sɪmˈplɪsəti", "The quality or condition of being easy to understand or do.", "He appreciated the simplicity of minimalist living.", "clarity, plainness", "complexity", "medium"),
        ("Household", "ˈhaʊshoʊld", "A house and its occupants regarded as a unit.", "Every household member shares the responsibility for chores.", "family, home", "", "easy"),
        ("Nourish", "ˈnɜːrɪʃ", "Provide with the food or other substances necessary for growth and health.", "A balanced diet helps nourish both body and mind.", "feed, nurture", "starve", "medium"),
        ("Spontaneous", "spɑːnˈteɪniəs", "Performed or occurring as a result of a sudden impulse without premeditation.", "We took a spontaneous road trip over the weekend.", "impulsive, unplanned", "planned, deliberate", "hard"),
        ("Serenity", "səˈrenəti", "The state of being calm, peaceful, and untroubled.", "Watching the ocean sunrise brought a sense of deep serenity.", "calmness, peace", "turmoil, chaos", "hard"),
        ("Bedtime", "ˈbedtaɪm", "The usual time at which someone goes to bed.", "Children need a consistent bedtime routine for healthy sleep.", "sleep time", "", "easy")
    ],
    "Travel & Tourism": [
        ("Itinerary", "aɪˈtɪnəreri", "A planned route or journey.", "Our European travel itinerary includes Paris, Rome, and Berlin.", "schedule, route", "", "medium"),
        ("Destination", "ˌdestɪˈneɪʃən", "The place to which someone or something is going or being sent.", "Bali is a popular holiday destination for beach lovers.", "target, endpoint", "origin", "easy"),
        ("Accommodation", "əˌkɑːməˈdeɪʃən", "A room, group of rooms, or building in which someone may live or stay.", "Hotel accommodation was booked well in advance of the festival.", "lodging, housing", "", "medium"),
        ("Souvenir", "ˌsuːvəˈnɪr", "A thing that is kept as a reminder of a person, place, or event.", "She bought a handmade ceramic bowl as a souvenir from Greece.", "memento, keepsake", "", "easy"),
        ("Passport", "ˈpæspɔːrt", "An official document issued by a government certifying identity and citizenship.", "Make sure your passport has at least six months of validity remaining.", "travel document", "", "easy"),
        ("Luggage", "ˈlʌɡɪdʒ", "Suitcases or other bags in which to pack personal belongings for traveling.", "The airline lost his luggage during the connecting flight.", "baggage, suitcases", "", "easy"),
        ("Boarding", "ˈbɔːrdɪŋ", "The action of getting on or into a ship, aircraft, or other vehicle.", "Boarding for flight AA123 will begin at gate number four.", "embarkation", "disembarkation", "easy"),
        ("Excursion", "ɪkˈskɜːrʒən", "A short journey or trip, especially one taken as a leisure activity.", "We booked a full-day excursion to explore the coral reef.", "trip, outing", "", "medium"),
        ("Picturesque", "ˌpɪktʃəˈresk", "Visually attractive, especially in a quaint or pretty style.", "The village is known for picturesque cobblestone streets and flower boxes.", "scenic, beautiful", "ugly, drab", "hard"),
        ("Backpacker", "ˈbækpækər", "A person who travels or hikes carrying their belongings in a backpack.", "Hostels cater mainly to young backpackers on a budget.", "hiker, traveler", "", "easy"),
        ("Customs", "ˈkʌstəmz", "The official department that administers and collects duties on imported goods.", "We declared our purchased goods at airport customs.", "border control", "", "medium"),
        ("Sightseeing", "ˈsaɪtsiːɪŋ", "The activity of visiting places of interest in a particular location.", "We spent the afternoon sightseeing around the ancient city ruins.", "touring, exploring", "", "easy"),
        ("Landmark", "ˈlændmɑːrk", "An object or feature of a landscape or town that is easily seen and recognized.", "The Eiffel Tower is the most famous landmark in Paris.", "monument, milestone", "", "easy"),
        ("Venture", "ˈventʃər", "Dare to do something or go into a challenging place.", "Few tourists venture into the dense mountainous wilderness alone.", "explore, risk", "retreat", "hard"),
        ("Jetlag", "ˈdʒetlæɡ", "Extreme tiredness caused by traveling across several time zones.", "Drinking plenty of water helps minimize the symptoms of jetlag.", "time-zone fatigue", "", "medium"),
        ("Reservation", "ˌrezərˈveɪʃən", "An arrangement by which accommodations are secured in advance.", "We have a dinner reservation for four at eight o'clock.", "booking", "cancellation", "easy"),
        ("Departure", "dɪˈpɑːrtʃər", "The action of leaving, especially to start a journey.", "Passengers gathered in the departure lounge before the flight.", "leaving, exit", "arrival", "easy"),
        ("Arrival", "əˈraɪvəl", "The action or process of arriving somewhere.", "Our scheduled arrival time in Tokyo is two in the afternoon.", "landing, coming", "departure", "easy"),
        ("Scenic", "ˈsiːnɪk", "Providing or relating to views of impressive natural scenery.", "The train ride offers a scenic view of snow-capped mountains.", "picturesque, panoramic", "dull, unattractive", "medium"),
        ("Voyage", "ˈvɔɪɪdʒ", "A long journey involving travel by sea or in space.", "The transatlantic voyage took seven days aboard the luxury cruise liner.", "journey, cruise", "", "medium"),
        ("Hospitality", "ˌhɑːspɪˈtæləti", "The friendly and generous reception and entertainment of guests.", "We were touched by the warm hospitality of the local villagers.", "warmth, friendliness", "hostility", "medium"),
        ("Ecotourism", "ˈiːkoʊtʊrɪzəm", "Tourism directed toward exotic, often threatened, natural environments.", "Costa Rica is a pioneer in sustainable ecotourism.", "green tourism", "", "hard"),
        ("Breathtaking", "ˈbreθteɪkɪŋ", "Astonishing or awe-inspiring in quality, so as to take one's breath away.", "The view from the mountain peak was absolutely breathtaking.", "stunning, magnificent", "ordinary, plain", "medium"),
        ("Guidebook", "ˈɡaɪdbʊk", "A book of information about a place designed for the use of visitors.", "The guidebook recommended several authentic local noodle shops.", "handbook, manual", "", "easy"),
        ("Transit", "ˈtrænzɪt", "The carrying of people or goods from one place to another.", "Passengers in transit remained inside the international terminal.", "transfer, transport", "", "medium"),
        ("Expedition", "ˌekspəˈdɪʃən", "A journey or voyage undertaken by a group of people with a particular purpose.", "Scientists launched an expedition to study polar glaciers.", "mission, trek", "", "hard"),
        ("Layover", "ˈleɪoʊvər", "A period of rest or waiting before a further stage in a journey.", "We had a four-hour layover in Dubai before our flight to London.", "stopover", "", "medium"),
        ("Exotic", "ɪɡˈzɑːtɪk", "Originating in or characteristic of a distant foreign country.", "The botanical garden features exotic plants from tropical rainforests.", "foreign, unusual", "native, familiar", "medium"),
        ("Monument", "ˈmɑːnjumənt", "A statue, building, or other structure erected to commemorate a notable person or event.", "The Washington Monument stands prominently on the National Mall.", "memorial, landmark", "", "medium"),
        ("Wanderlust", "ˈwɑːndərlʌst", "A strong desire to travel.", "Her wanderlust inspired her to visit over thirty countries before thirty.", "travel bug", "", "hard"),
        ("Luggage Carousel", "ˈlʌɡɪdʒ ˌkærəˈsel", "A conveyor belt system at an airport from which passengers collect their bags.", "We waited at luggage carousel number three for our suitcases.", "baggage claim", "", "medium"),
        ("Embark", "ɪmˈbɑːrk", "Go on board a ship, aircraft, or other vehicle.", "Passengers will embark on the cruise ship tomorrow morning.", "board, set sail", "disembark", "hard"),
        ("Disembark", "ˌdɪsɪmˈbɑːrk", "Leave a ship, aircraft, or other vehicle.", "Please ensure you have all personal items before you disembark.", "alight, exit", "embark", "hard"),
        ("Cruise", "kruːz", "A voyage on a ship or boat taken for pleasure.", "They celebrated their anniversary on a Caribbean cruise.", "sail, voyage", "", "easy"),
        ("Immigration", "ˌɪmɪˈɡreɪʃən", "The place at an airport or port where the passports and visas of travelers are checked.", "Passport control and immigration lines were surprisingly fast today.", "border inspection", "", "medium")
    ],
    "Education & Study": [
        ("Curriculum", "kəˈrɪkjələm", "The subjects comprising a course of study in a school or college.", "The updated science curriculum emphasizes hands-on experiments.", "syllabus, program", "", "medium"),
        ("Assignment", "əˈsaɪnmənt", "A task or piece of work allocated to someone as part of a course.", "The history assignment is due next Monday before noon.", "homework, project", "", "easy"),
        ("Scholarship", "ˈskɑːlərʃɪp", "A grant or payment made to support a student's education.", "She was awarded a full scholarship based on academic merit.", "grant, fellowship", "", "medium"),
        ("Syllabus", "ˈsɪləbəs", "An outline of the subjects in a course of study or teaching.", "The professor handed out the course syllabus on the first day of class.", "course outline", "", "medium"),
        ("Lecture", "ˈlektʃər", "An educational talk to an audience, especially to students in a university.", "Over three hundred undergraduates attended the economics lecture.", "presentation, address", "", "easy"),
        ("Tuition", "tuːˈɪʃən", "A sum of money charged for teaching or instruction by a school or university.", "Many students take out loans to cover rising university tuition.", "fees, school costs", "", "medium"),
        ("Semester", "səˈmestər", "A half-year term in a school or college, typically lasting for fifteen to eighteen weeks.", "Final examinations take place at the end of every semester.", "term, session", "", "easy"),
        ("Plagiarism", "ˈpleɪdʒərɪzəm", "The practice of taking someone else's work or ideas and passing them off as one's own.", "The university has a strict zero-tolerance policy regarding plagiarism.", "copying, theft", "originality", "hard"),
        ("Dissertation", "ˌdɪsərˈteɪʃən", "A long essay on a particular subject, especially written for a university degree.", "She spent three years conducting research for her doctoral dissertation.", "thesis, treatise", "", "hard"),
        ("Extracurricular", "ˌekstrəkəˈrɪkjələr", "Pursued in addition to the normal course of study.", "Participating in extracurricular sports builds teamwork and leadership skills.", "after-school", "curricular", "medium"),
        ("Faculty", "ˈfækəlti", "The teaching staff of a university or college.", "The engineering faculty includes world-renowned roboticists.", "professors, staff", "students", "medium"),
        ("Academic", "ˌækəˈdemɪk", "Relating to education and scholarship.", "He has built an outstanding academic record over his four years of study.", "scholarly, educational", "practical", "easy"),
        ("Pedagogy", "ˈpedəɡɑːdʒi", "The method and practice of teaching, especially as an academic subject.", "Modern pedagogy focuses on student-centered interactive learning.", "teaching method", "", "hard"),
        ("Graduate", "ˈɡrædʒueɪt", "A person who has successfully completed a course of study or degree.", "She is a recent graduate of Stanford University.", "alumnus, degree-holder", "undergraduate", "easy"),
        ("Diploma", "dɪˈploʊmə", "A certificate awarded by an educational establishment.", "He proudly framed his high school diploma on his office wall.", "certificate, degree", "", "easy"),
        ("Literacy", "ˈlɪtərəsi", "The ability to read and write.", "The NGO launched an initiative to improve digital literacy among seniors.", "reading ability", "illiteracy", "medium"),
        ("Enrollment", "ɪnˈroʊlmənt", "The action of enrolling or being enrolled.", "University enrollment increased by fifteen percent this autumn.", "registration, admission", "withdrawal", "medium"),
        ("Prerequisite", "priːˈrekwəzɪt", "A thing that is required as a prior condition for something else to happen.", "Calculus I is a mandatory prerequisite for advanced physics.", "requirement, precondition", "", "hard"),
        ("Evaluation", "ɪˌvæljuˈeɪʃən", "The making of a judgment about the amount, number, or value of something.", "The semester evaluation assesses classroom performance and essays.", "assessment, appraisal", "", "medium"),
        ("Quiz", "kwɪz", "A test of knowledge, especially as a competition or classroom activity.", "We had a ten-question vocabulary quiz in French class today.", "test, exam", "", "easy"),
        ("Tutor", "ˈtuːtər", "A private teacher, typically one who teaches a single student or a very small group.", "She hired a math tutor to prepare for the university entrance exam.", "instructor, coach", "", "easy"),
        ("Alumni", "əˈlʌmnaɪ", "Former students of a particular school, college, or university.", "The alumni association raised funds for a new student library.", "graduates", "", "medium"),
        ("Compulsory", "kəmˈpʌlsəri", "Required by law or a rule; obligatory.", "Primary education is compulsory for all children aged six to fourteen.", "mandatory, required", "optional, voluntary", "hard"),
        ("Internship", "ˈɪntɜːrnʃɪp", "The position of a student or trainee who works in an organization.", "He completed a summer internship at a biomedical laboratory.", "training, apprenticeship", "", "medium"),
        ("Mentor", "ˈmentɔːr", "An experienced and trusted adviser.", "Her senior colleague served as an invaluable career mentor.", "guide, adviser", "mentee", "easy"),
        ("Proctor", "ˈprɑːktər", "A person who monitors students during an examination.", "The exam proctor instructed candidates to put away their phones.", "invigilator, supervisor", "", "hard"),
        ("Discipline", "ˈdɪsəplɪn", "A branch of knowledge, typically one studied in higher education.", "Neuroscience is an interdisciplinary field combining multiple scientific disciplines.", "field, subject", "", "medium"),
        ("Cognitive", "ˈkɑːɡnətɪv", "Relating to the mental action or process of acquiring knowledge.", "Puzzles and flashcards help maintain sharp cognitive functions.", "mental, intellectual", "physical", "hard"),
        ("Comprehension", "ˌkɑːmprɪˈhenʃən", "The action or capability of understanding something.", "Reading comprehension exercises improve vocabulary retention.", "understanding, grasp", "confusion", "medium"),
        ("Cram", "kræm", "Study intensively over a short period of time just before an examination.", "It is better to study consistently than to cram the night before an exam.", "swot, bone up", "", "medium"),
        ("Retention", "rɪˈtenʃən", "The continued possession, use, or control of something; the ability to remember.", "Spaced repetition significantly improves long-term memory retention.", "recall, memory", "forgetfulness", "hard"),
        ("Thesis", "ˈθiːsɪs", "A statement or theory that is put forward as a premise to be maintained or proved.", "His master's thesis focused on renewable energy policy.", "dissertation, proposition", "", "medium"),
        ("Transcript", "ˈtrænskrɪpt", "An official record of a student's work, showing courses taken and grades achieved.", "Submit an official academic transcript along with your application.", "grade report", "", "medium"),
        ("Valedictorian", "ˌvælədɪkˈtɔːriən", "A student who delivers the valedictory speech at a graduation ceremony, typically the top-ranked.", "The valedictorian delivered an inspiring speech to the graduating class.", "top graduate", "", "hard"),
        ("Workshop", "ˈwɜːrkʃɑːp", "A meeting at which a group of people engage in intensive discussion and activity.", "The university hosted a workshop on scientific writing.", "seminar, session", "", "easy")
    ],
    "Business & Workplace": [
        ("Negotiation", "nɪˌɡoʊʃiˈeɪʃən", "Discussion aimed at reaching an agreement.", "Contract negotiations concluded successfully after weeks of dialogue.", "bargaining, discussion", "", "medium"),
        ("Colleague", "ˈkɑːliːɡ", "A person with whom one works in a profession or business.", "She collaborated with her colleagues to finish the marketing report.", "coworker, associate", "competitor", "easy"),
        ("Stakeholder", "ˈsteɪkhoʊldər", "A person with an interest or concern in something, especially a business.", "We presented the quarterly financial forecast to key stakeholders.", "investor, shareholder", "", "medium"),
        ("Deadline", "ˈdedlaɪn", "The latest time or date by which something should be completed.", "The team worked overtime to meet the project deadline.", "due date, cutoff", "", "easy"),
        ("Agile", "ˈædʒl", "Relating to a method of project management characterized by the division of tasks into short phases.", "Our software team adopted an agile workflow with daily standups.", "flexible, nimble", "rigid", "medium"),
        ("Productivity", "ˌproʊdʌkˈtɪvəti", "The effectiveness of productive effort, especially in industry.", "Ergonomic office chairs improve employee productivity and comfort.", "efficiency, output", "idleness", "medium"),
        ("Delegate", "ˈdelɪɡeɪt", "Entrust a task or responsibility to another person, typically one who is less senior.", "Effective leaders know how to delegate tasks to capable team members.", "assign, entrust", "retain", "hard"),
        ("Benchmark", "ˈbentʃmɑːrk", "A standard or point of reference against which things may be compared or assessed.", "The company's customer service sets the benchmark for the entire industry.", "standard, criterion", "", "hard"),
        ("Milestone", "ˈmaɪlstoʊn", "A significant stage or event in the development of something.", "Securing our first thousand paying users was a major milestone.", "achievement, breakthrough", "", "medium"),
        ("Synergy", "ˈsɪnərdʒi", "The interaction or cooperation of two or more organizations to produce a combined effect greater than the sum.", "The merger created synergy between the sales and development teams.", "cooperation, harmony", "conflict", "hard"),
        ("Outsource", "ˈaʊtsɔːrs", "Obtain goods or services from an outside or foreign supplier.", "Many tech startups outsource accounting to specialized agencies.", "contract out", "in-source", "medium"),
        ("Revenue", "ˈrevənuː", "Income, especially when of a company or organization and of a substantial nature.", "Quarterly revenue increased by twenty percent compared to last year.", "income, earnings", "expenditure, loss", "medium"),
        ("Overhead", "ˈoʊvərhed", "An ongoing expense of operating a business.", "Remote work reduced corporate overhead costs like office rent.", "operating cost", "", "hard"),
        ("Appraisal", "əˈpreɪzəl", "An act of assessing something or someone.", "Annual performance appraisals determine promotion eligibility.", "evaluation, assessment", "", "hard"),
        ("Hierarchy", "ˈhaɪərɑːrki", "A system or organization in which people or groups are ranked one above the other.", "The corporate hierarchy consists of entry-level staff, managers, and executives.", "ranking, chain of command", "", "hard"),
        ("Entrepreneur", "ˌɑːntrəprəˈnɜːr", "A person who sets up a business, taking on financial risks in the hope of profit.", "The young entrepreneur launched a sustainable packaging company.", "businessperson, founder", "", "medium"),
        ("Clientele", "ˌklaɪənˈtel", "The customers of a shop, bar, or other business.", "The boutique hotel caters to an international business clientele.", "customers, patrons", "", "hard"),
        ("Quota", "ˈkwoʊtə", "A limited or fixed number or amount of people or things, in particular sales.", "Sales representatives exceeded their monthly sales quota.", "target, allocation", "", "medium"),
        ("Supervise", "ˈsuːpərvaɪz", "Observe and direct the execution of a task, project, or activity.", "The project director will supervise the construction site.", "oversee, manage", "", "easy"),
        ("Incentive", "ɪnˈsentɪv", "A thing that motivates or encourages someone to do something.", "Annual bonuses serve as a strong performance incentive.", "motivation, stimulus", "deterrent", "medium"),
        ("Severance", "ˈsevərəns", "An amount paid to an employee on the early termination of an agreement.", "Employees who were laid off received six months of severance pay.", "severance package", "", "hard"),
        ("Consensus", "kənˈsensəs", "A general agreement.", "The board reached a consensus on expanding into European markets.", "agreement, harmony", "disagreement", "medium"),
        ("Compliance", "kəmˈplaɪəns", "The state or fact of according with or meeting rules or standards.", "The legal department ensures full compliance with privacy laws.", "conformity, adherence", "violation", "hard"),
        ("Consultant", "kənˈsʌltənt", "A person who provides expert advice professionally.", "We hired a management consultant to streamline our operations.", "adviser, specialist", "", "medium"),
        ("Turnover", "ˈtɜːrnoʊvər", "The rate at which employees leave a workforce and are replaced.", "Flexible working hours helped reduce employee turnover.", "attrition", "retention", "medium"),
        ("Venture Capital", "ˈventʃər ˈkæpɪtl", "Capital invested in a project in which there is a substantial element of risk.", "The AI startup secured five million dollars in venture capital.", "investment funding", "", "medium"),
        ("Whiteboard", "ˈwaɪtbɔːrd", "A wipeable board with a white surface used for teaching or presentations.", "We mapped out the user flow on the conference room whiteboard.", "marker board", "", "easy"),
        ("Briefing", "ˈbriːfɪŋ", "A meeting for giving information or instructions.", "The captain held a morning briefing before the deployment.", "meeting, summary", "", "easy"),
        ("Disruption", "dɪsˈrʌpʃən", "Disturbance or problems which interrupt an event, activity, or process.", "Digital streaming caused major disruption to the traditional film industry.", "interruption, turmoil", "stability", "medium"),
        ("Monopoly", "məˈnɑːpəli", "The exclusive possession or control of the supply of or trade in a commodity or service.", "Anti-trust regulations prevent any single firm from creating a monopoly.", "exclusive control", "competition", "hard"),
        ("Proactive", "proʊˈæktɪv", "Creating or controlling a situation rather than just responding to it.", "Taking a proactive approach prevents customer complaints before they happen.", "enterprising, forward-looking", "reactive, passive", "medium"),
        ("Logistics", "ləˈdʒɪstɪks", "The detailed coordination of a complex operation involving many people, facilities, or supplies.", "The logistics team ensured timely delivery of inventory worldwide.", "coordination, supply chain", "", "hard"),
        ("Portfolio", "pɔːrtˈfoʊlioʊ", "A range of investments held by a person or organization; a collection of work.", "The designer presented a portfolio of web development projects.", "collection, holdings", "", "medium"),
        ("Vendor", "ˈvendər", "A person or company offering something for sale, especially a trader in the street.", "The company works with trusted hardware vendors for office equipment.", "seller, supplier", "buyer, purchaser", "medium"),
        ("Workforce", "ˈwɜːrkfɔːrs", "The people engaged in or available for work, either in a country or area or in a particular company.", "The tech firm employs a diverse workforce spanning fifteen countries.", "employees, staff", "", "easy")
    ],
    "Technology & AI": [
        ("Algorithm", "ˈælɡərɪðəm", "A process or set of rules to be followed in calculations or problem-solving operations.", "Recommendation algorithms suggest videos based on your watch history.", "procedure, rule-set", "", "medium"),
        ("Neural Network", "ˈnʊrəl ˈnetwɜːrk", "A computer system modeled on the human brain and nervous system.", "Deep neural networks are used for advanced computer vision and voice recognition.", "deep learning model", "", "hard"),
        ("Automation", "ˌɔːtəˈmeɪʃən", "The use of largely automatic equipment in a system of manufacturing or other production.", "Factory automation reduced assembly errors by ninety percent.", "mechanization, robotics", "manual labor", "medium"),
        ("Cybersecurity", "ˈsaɪbərsɪˌkjʊrəti", "The state of being protected against the criminal or unauthorized use of electronic data.", "Banks invest heavily in cybersecurity to protect customer accounts.", "data security, info-sec", "", "medium"),
        ("Bandwidth", "ˈbændwɪdθ", "The maximum data transfer rate of a network or internet connection.", "High-definition video streaming requires adequate internet bandwidth.", "network capacity", "", "medium"),
        ("Cloud Computing", "klaʊd kəmˈpjuːtɪŋ", "The practice of using a network of remote servers hosted on the internet to store, manage, and process data.", "Cloud computing allows businesses to scale server resources on demand.", "hosted services", "on-premise", "medium"),
        ("Interface", "ˈɪntərfeɪs", "A point where two systems, subjects, organizations, etc. meet and interact.", "The mobile app features an intuitive graphical user interface.", "UI, connection", "", "easy"),
        ("Encryption", "ɪnˈkrɪpʃən", "The process of converting information or data into a code, especially to prevent unauthorized access.", "End-to-end encryption ensures that only sender and recipient can read the message.", "ciphering, encoding", "decryption, decoding", "hard"),
        ("Latency", "ˈleɪtnsi", "The delay before a transfer of data begins following an instruction for its transfer.", "Low latency is critical for real-time online gaming and video calls.", "delay, lag", "speed, immediacy", "hard"),
        ("Database", "ˈdeɪtəbeɪs", "A structured set of data held in a computer, especially one that is accessible in various ways.", "PostgreSQL is a powerful relational database.", "data repository", "", "easy"),
        ("Biometrics", "ˌbaɪoʊˈmetrɪks", "The measurement and statistical analysis of people's unique physical characteristics.", "Facial recognition and fingerprint scanners are common forms of biometrics.", "biological authentication", "", "hard"),
        ("Open-Source", "ˈoʊpən sɔːrs", "Denoting software for which the original source code is made freely available and may be redistributed.", "Linux is the most famous open-source operating system in the world.", "free software", "proprietary, closed-source", "easy"),
        ("Malware", "ˈmælwer", "Software that is specifically designed to disrupt, damage, or gain unauthorized access to a computer system.", "Regular antivirus scans protect your PC from dangerous malware.", "virus, spyware", "security software", "medium"),
        ("Scalability", "ˌskeɪləˈbɪləti", "The capability of a system, network, or process to handle a growing amount of work.", "The microservices architecture provides excellent horizontal scalability.", "expandability", "rigidity", "hard"),
        ("Virtual Reality", "ˈvɜːrtʃuəl riˈæləti", "The computer-generated simulation of a three-dimensional image or environment.", "Virtual reality headsets provide an immersive flight simulation training experience.", "VR, simulated environment", "", "easy"),
        ("Framework", "ˈfreɪmwɜːrk", "A basic structure underlying a system, concept, or text, especially a software package.", "Flask is a lightweight web framework for building Python web applications.", "platform, structure", "", "medium"),
        ("Repository", "rɪˈpɑːzətɔːri", "A central place where data or code is stored and maintained.", "Developers push their daily commits to the GitHub repository.", "repo, code vault", "", "medium"),
        ("Prompt", "prɑːmpt", "An instruction or query given to an artificial intelligence model.", "Writing a precise prompt helps the AI generate accurate code snippets.", "instruction, input", "", "easy"),
        ("Firmware", "ˈfɜːrmwer", "Permanent software programmed into a read-only memory.", "Updating the router firmware fixed the Wi-Fi connectivity bug.", "embedded software", "", "hard"),
        ("Hardware", "ˈhɑːrdwer", "The physical components of a computer system.", "A graphics processing unit is an essential piece of hardware for AI training.", "physical equipment", "software", "easy"),
        ("Phishing", "ˈfɪʃɪŋ", "The fraudulent practice of sending emails purporting to be from reputable companies in order to steal data.", "Never click unknown links to avoid falling for phishing scams.", "fraud, scam", "", "medium"),
        ("Bandwidth Throttling", "ˈbændwɪdθ ˈθrɑːtlɪŋ", "The intentional slowing of internet service by an internet service provider.", "The ISP engaged in bandwidth throttling during peak evening hours.", "speed limiting", "", "hard"),
        ("Bug", "bʌɡ", "An error, flaw, or fault in a computer program or system.", "The software update patched a critical security bug.", "glitch, defect", "feature", "easy"),
        ("Patch", "pætʃ", "A piece of software designed to update a computer program or its supporting data.", "System administrators applied the security patch immediately.", "fix, update", "", "easy"),
        ("Token", "ˈtoʊkən", "A piece of data that represents a unit of text in AI or a secure session key.", "The language model processes input in chunks called tokens.", "identifier, chunk", "", "medium"),
        ("Semiconductor", "ˌsemikənˈdʌktər", "A solid substance that has a conductivity between that of an insulator and that of most metals.", "Silicon microchips are the most vital semiconductor components in electronics.", "microchip, transistor", "", "hard"),
        ("Quantum", "ˈkwɑːntəm", "Relating to quantum mechanics; a discrete quantity of energy.", "Quantum computing promises exponential leaps in computational speed.", "atomic, subatomic", "classical", "hard"),
        ("Server", "ˈsɜːrvər", "A computer or computer program that manages access to a centralized resource or service in a network.", "The web server handles thousands of concurrent HTTP requests.", "host, mainframe", "client", "easy"),
        ("Domain", "doʊˈmeɪn", "An identification string that defines a realm of administrative autonomy on the internet.", "We registered a custom domain name for our new online store.", "web address, URL", "", "easy"),
        ("Protocol", "ˈproʊtəkɑːl", "A set of rules governing the exchange or transmission of data between devices.", "HTTPS is the secure protocol for modern web browsing.", "standard, rule", "", "medium"),
        ("Browser", "ˈbraʊzər", "A computer program with a graphical user interface for displaying and navigating web pages.", "Google Chrome and Mozilla Firefox are popular web browsers.", "web client", "", "easy"),
        ("Cache", "kæʃ", "A hardware or software component that stores data so that future requests for that data can be served faster.", "Clear your browser cache if the website fails to load updated styles.", "buffer, storehouse", "", "medium"),
        ("Compiler", "kəmˈpaɪlər", "A program that translates source code into machine code.", "The Rust compiler caught the memory safety violation before runtime.", "code translator", "interpreter", "hard"),
        ("Deploy", "dɪˈplɔɪ", "Bring into effective action; publish an application to a production server.", "We deploy our Flask web service to Render using Gunicorn.", "release, publish", "rollback", "medium"),
        ("Heuristic", "hjuˈrɪstɪk", "Enabling a person to discover or learn something for themselves; a practical problem-solving shortcut.", "Search engines use heuristic algorithms to rank search results quickly.", "rule of thumb, shortcut", "", "hard")
    ],
    "Food & Dining": [
        ("Appetizer", "ˈæpɪtaɪzər", "A small dish of food or a drink taken before a meal or the main course.", "We ordered crispy calamari as an appetizer.", "starter, hors d'oeuvre", "dessert", "easy"),
        ("Entree", "ˈɑːntreɪ", "The main course of a meal.", "For my entree, I chose the grilled salmon with roasted vegetables.", "main course, main dish", "appetizer", "easy"),
        ("Beverage", "ˈbevərɪdʒ", "A drink, especially one other than water.", "The flight attendant offered coffee, tea, and other cold beverages.", "drink, refreshment", "food", "easy"),
        ("Culinary", "ˈkʌlɪneri", "Of or for cooking or the kitchen.", "She enrolled in a world-famous culinary institute to become a chef.", "cooking, gastronomic", "", "medium"),
        ("Ingredient", "ɪnˈɡriːdiənt", "Any of the foods or substances that are combined to make a particular dish.", "Fresh basil is an essential ingredient in traditional Italian pesto.", "component, element", "", "easy"),
        ("Nutritious", "nuːˈtrɪʃəs", "Nourishing, efficient as food.", "A bowl of oatmeal with berries makes a nutritious breakfast.", "healthy, wholesome", "unhealthy, junk", "easy"),
        ("Delicacy", "ˈdelɪkəsi", "A choice or expensive food.", "Caviar and truffles are considered luxury delicacies worldwide.", "treat, specialty", "", "medium"),
        ("Gourmet", "ɡʊrˈmeɪ", "Involving or of high quality, delicious, or elaborate food.", "The city is famous for its gourmet restaurants and award-winning bakeries.", "fine food, exquisite", "plain, low-grade", "medium"),
        ("Vegetarian", "ˌvedʒəˈteriən", "A person who does not eat meat or fish, and sometimes other animal products.", "The cafe offers a wide variety of vegan and vegetarian options.", "plant-based", "carnivore", "easy"),
        ("Seasoning", "ˈsiːzənɪŋ", "Salt, herbs, or spices added to food to enhance its flavor.", "A touch of garlic seasoning brought out the rich flavor of the steak.", "spices, flavor", "", "easy"),
        ("Savor", "ˈseɪvər", "Taste good food or drink and enjoy it completely.", "Take your time to savor every bite of this homemade dessert.", "enjoy, relish", "", "medium"),
        ("Aroma", "əˈroʊmə", "A pleasant and distinctive smell.", "The rich aroma of freshly ground espresso filled the room.", "fragrance, scent", "stench, odor", "easy"),
        ("Buffet", "bəˈfeɪ", "A meal consisting of several dishes from which guests serve themselves.", "The hotel served an extensive all-you-can-eat breakfast buffet.", "smorgasbord, self-service", "a la carte", "easy"),
        ("Palatable", "ˈpælətəbl", "Pleasant to taste; acceptable or satisfactory.", "Adding a pinch of sugar made the bitter medicine much more palatable.", "tasty, appetizing", "unpalatable, foul", "hard"),
        ("Ferment", "fərˈment", "Undergo or cause to undergo fermentation.", "Kimchi and yogurt are fermented foods that support healthy gut bacteria.", "brew, age", "", "hard"),
        ("Marinate", "ˈmærɪneɪt", "Soak meat, fish, or other food in a marinade before cooking.", "Marinate the chicken in olive oil, lemon juice, and herbs for two hours.", "soak, steep", "", "medium"),
        ("Garnish", "ˈɡɑːrnɪʃ", "Decorate or embellish something, especially food.", "Garnish the creamy soup with freshly chopped parsley.", "decorate, adorn", "", "medium"),
        ("Allergy", "ˈælərdʒi", "A damaging immune response by the body to a substance, especially food.", "Please inform the waiter if you have a severe peanut allergy.", "hypersensitivity", "immunity", "easy"),
        ("Portion", "ˈpɔːrʃən", "The amount of food served for one person.", "The restaurant is famous for serving generous portion sizes.", "serving, helping", "", "easy"),
        ("Dessert", "dɪˈzɜːrt", "The sweet course eaten at the end of a meal.", "We ordered tiramisu and strawberry cheesecake for dessert.", "sweet, pudding", "appetizer", "easy"),
        ("Pastry", "ˈpeɪstri", "A dough of flour, fat, and water, used as a base and covering in baked dishes.", "French croissants are celebrated for their flaky, buttery pastry layers.", "baked good", "", "easy"),
        ("Spicy", "ˈspaɪsi", "Flavored with or fragrant with spice; hot to the taste.", "Thai tom yum soup is wonderfully spicy and aromatic.", "hot, pungent", "mild, bland", "easy"),
        ("Crispy", "ˈkrɪspi", "Pleasantly thin, dry, and easily broken; having a pleasingly firm, dry texture.", "The fried chicken has a crispy golden-brown skin.", "crunchy, brittle", "soggy, soft", "easy"),
        ("Tender", "ˈtendər", "Easy to cut or chew; not tough.", "Slow-cooking makes beef brisket exceptionally tender and juicy.", "soft, succulent", "tough, hard", "easy"),
        ("Savory", "ˈseɪvəri", "Belonging to the category that is salty or spicy rather than sweet.", "We enjoyed a savory quiche with spinach and goat cheese.", "salty, flavorful", "sweet", "medium"),
        ("Bland", "blænd", "Lacking strong features or characteristics and therefore uninteresting, especially in food flavor.", "Without salt and pepper, the boiled potatoes tasted rather bland.", "tasteless, dull", "flavorful, spicy", "easy"),
        ("Satiate", "ˈseɪʃieɪt", "Satisfy a desire or an appetite to the full.", "A hearty bowl of beef stew is enough to satiate any hungry hiker.", "satisfy, fill", "deprive", "hard"),
        ("Cutlery", "ˈkʌtləri", "Knives, forks, and spoons used for eating or serving food.", "Set the silverware and cutlery neatly beside each plate.", "silverware, utensils", "", "medium"),
        ("Sommelier", "ˌsʌməlˈjeɪ", "A wine waiter or steward.", "The restaurant sommelier recommended an exquisite Pinot Noir.", "wine expert", "", "hard"),
        ("Organic", "ɔːrˈɡænɪk", "Produced without the use of chemical fertilizers, pesticides, or artificial agents.", "The market sells certified organic fruits and vegetables.", "natural, bio", "conventional", "easy"),
        ("Pungent", "ˈpʌndʒənt", "Having a sharply strong taste or smell.", "Freshly crushed garlic has a distinctive, pungent odor.", "sharp, strong", "mild, faint", "hard"),
        ("Leftovers", "ˈleftoʊvərz", "Food remaining uneaten at the end of a meal.", "We packed the pizza leftovers for lunch the next day.", "remains, extra food", "", "easy"),
        ("Banquet", "ˈbæŋkwɪt", "An elaborate and formal evening meal for many people, often followed by speeches.", "The university hosted a celebratory banquet for graduating scholars.", "feast, dinner", "", "medium"),
        ("Appetite", "ˈæpɪtaɪt", "A natural desire to satisfy a bodily need, especially for food.", "A long mountain hike always gives me a healthy appetite.", "hunger, desire", "satiety", "easy"),
        ("Recipe", "ˈresəpi", "A set of instructions for preparing a particular dish, including a list of the ingredients required.", "Grandmother shared her secret recipe for homemade apple pie.", "formula, instructions", "", "easy")
    ],
    "Health & Medicine": [
        ("Diagnosis", "ˌdaɪəɡˈnoʊsɪs", "The identification of the nature of an illness or other problem by examination of the symptoms.", "An early diagnosis greatly improves the success rate of medical treatment.", "identification, assessment", "", "medium"),
        ("Prescription", "prɪˈskrɪpʃən", "An instruction written by a medical practitioner that authorizes a patient to be provided a medicine.", "Take this prescription to the local pharmacy to pick up your antibiotics.", "medicine order, script", "", "easy"),
        ("Symptom", "ˈsɪmptəm", "A physical or mental feature which is regarded as indicating a condition of disease.", "A high fever and persistent cough are common symptoms of the flu.", "indication, sign", "", "easy"),
        ("Immunity", "ɪˈmjuːnəti", "The ability of an organism to resist a particular infection or toxin.", "Vaccinations help the body build lasting immunity against diseases.", "resistance, protection", "vulnerability", "medium"),
        ("Therapy", "ˈθerəpi", "Treatment intended to relieve or heal a disorder.", "Physical therapy helped him regain full mobility in his shoulder.", "treatment, rehabilitation", "", "easy"),
        ("Chronic", "ˈkrɑːnɪk", "Persisting for a long time or constantly recurring.", "Yoga and stretching can help manage chronic back pain.", "long-term, persistent", "acute, temporary", "medium"),
        ("Antibiotic", "ˌæntibaɪˈɑːtɪk", "A medicine that inhibits the growth of or destroys microorganisms.", "Complete the full course of antibiotics as directed by your physician.", "antimicrobial", "", "easy"),
        ("Rehabilitation", "ˌriːhəˌbɪlɪˈteɪʃən", "The action of restoring someone to health or normal life through training and therapy.", "The sports clinic specializes in post-surgery knee rehabilitation.", "recovery, rehab", "", "hard"),
        ("Vaccine", "vækˈsiːn", "A biological preparation that provides active acquired immunity to a particular infectious disease.", "Children receive routine vaccines to protect against measles and mumps.", "immunization", "", "easy"),
        ("Physician", "fɪˈzɪʃən", "A person qualified to practice medicine.", "Consult your primary care physician before starting a rigorous exercise program.", "doctor, clinician", "", "easy"),
        ("Epidemic", "ˌepɪˈdemɪk", "A widespread occurrence of an infectious disease in a community at a particular time.", "Public health officials worked tirelessly to contain the cholera epidemic.", "outbreak, plague", "endemic", "medium"),
        ("Cardiovascular", "ˌkɑːrdioʊˈvæskjələr", "Relating to the heart and blood vessels.", "Aerobic exercise like running strengthens cardiovascular endurance.", "circulatory", "", "hard"),
        ("Nutrient", "ˈnuːtriənt", "A substance that provides nourishment essential for growth and the maintenance of life.", "Leafy greens are packed with vital vitamins and essential nutrients.", "nourishment, mineral", "", "medium"),
        ("Hypertension", "ˌhaɪpərˈtenʃən", "Abnormally high blood pressure.", "Reducing dietary sodium intake is a key step in managing hypertension.", "high blood pressure", "hypotension", "hard"),
        ("Allergic", "əˈlɜːrdʒɪk", "Caused by or relating to an allergy.", "He is allergic to cat fur and experiences sneezing around pets.", "sensitive, hypersensitive", "immune", "easy"),
        ("Sedentary", "ˈsednteri", "Characterized by much sitting and little physical exercise.", "A sedentary lifestyle increases the risk of metabolic and heart diseases.", "inactive, motionless", "active", "hard"),
        ("Insomnia", "ɪnˈsɑːmniə", "Habitual sleeplessness; inability to sleep.", "Stress and screen exposure late at night can trigger chronic insomnia.", "sleeplessness", "", "medium"),
        ("Metabolism", "məˈtæbəlɪzəm", "The chemical processes that occur within a living organism in order to maintain life.", "Regular strength training helps boost resting metabolism.", "energy expenditure", "", "hard"),
        ("Prognosis", "prɑːɡˈnoʊsɪs", "The likely course of a medical condition.", "With timely surgery, the patient's long-term prognosis is excellent.", "outlook, forecast", "", "hard"),
        ("Contagious", "kənˈteɪdʒəs", "Spread from one person or organism to another by direct or indirect contact.", "The common cold is highly contagious in crowded classrooms.", "infectious, transmissible", "non-contagious", "medium"),
        ("Anesthesia", "ˌænəsˈθiːʒə", "Insensitivity to pain, especially as artificially induced by the administration of gases or the injection of drugs.", "The surgeon waited for the general anesthesia to take full effect.", "painlessness, sedation", "", "hard"),
        ("Fatigue", "fəˈtiːɡ", "Extreme tiredness resulting from mental or physical exertion or illness.", "Adequate sleep and balanced nutrition alleviate mental fatigue.", "exhaustion, tiredness", "energy", "medium"),
        ("Sedative", "ˈsedətɪv", "A drug taken for its calming or sleep-inducing effect.", "The doctor prescribed a mild sedative to help with acute anxiety.", "tranquilizer, calming agent", "stimulant", "hard"),
        ("Vitality", "vaɪˈtæləti", "The state of being strong and active; energy.", "A healthy lifestyle restores youthful vigor and vitality.", "energy, vigor", "lethargy, weakness", "medium"),
        ("Resilient", "rɪˈzɪliənt", "Able to withstand or recover quickly from difficult conditions.", "Children's immune systems are remarkably resilient when well-nourished.", "tough, adaptable", "fragile, vulnerable", "medium"),
        ("Disorder", "dɪsˈɔːrdər", "A disruption of normal physical or mental functions; a disease or abnormal condition.", "She sought therapy to cope with a seasonal affective disorder.", "ailment, condition", "health", "medium"),
        ("Pharmaceutical", "ˌfɑːrməˈsuːtɪkl", "Relating to medicinal drugs, or their preparation, use, or sale.", "The pharmaceutical company patented a novel asthma medication.", "medicinal, drug-related", "", "hard"),
        ("Sterilize", "ˈsterəlaɪz", "Make something free from bacteria or other living microorganisms.", "Surgeons must carefully sterilize all instruments prior to an operation.", "disinfect, sanitize", "contaminate", "medium"),
        ("Toxicity", "tɑːkˈsɪsəti", "The quality of being toxic or poisonous.", "Laboratory tests verified that the cosmetic product has zero toxicity.", "poisonousness, harmfulness", "safety", "hard"),
        ("Ointment", "ˈɔɪntmənt", "A smooth oily substance that is rubbed on the skin for medicinal purposes.", "Apply this soothing antibacterial ointment to the minor scrape.", "salve, cream", "", "easy"),
        ("Physiotherapy", "ˌfɪzioʊˈθerəpi", "The treatment of disease, injury, or deformity by physical methods such as massage and heat treatment.", "He attends physiotherapy twice a week following knee ligament surgery.", "physical therapy", "", "hard"),
        ("Checkup", "ˈtʃekʌp", "A thorough medical or physical examination.", "Adults should schedule an annual health checkup with their doctor.", "medical examination", "", "easy"),
        ("Inflammation", "ˌɪnfləˈmeɪʃən", "A localized physical condition in which part of the body becomes reddened, swollen, hot, and often painful.", "Ice packs help reduce tissue inflammation after an ankle sprain.", "swelling, soreness", "", "medium"),
        ("Optometrist", "ɑːpˈtɑːmətrɪst", "A person who practices optometry; an eye specialist.", "The optometrist measured my vision and prescribed new reading glasses.", "eye doctor", "", "hard"),
        ("Well-being", "ˈwel biːɪŋ", "The state of being comfortable, healthy, or happy.", "Mindfulness exercises significantly improve mental and emotional well-being.", "health, happiness", "misery", "easy")
    ],
    "Environment & Nature": [
        ("Biodiversity", "ˌbaɪoʊdaɪˈvɜːrsəti", "The variety of plant and animal life in the world or in a particular habitat.", "Deforestation in the Amazon rainforest threatens global biodiversity.", "biological variety", "", "medium"),
        ("Sustainability", "səˌsteɪnəˈbɪləti", "The ability to be maintained at a certain rate or level without exhausting natural resources.", "Renewable solar energy is vital for environmental sustainability.", "conservation, ecological balance", "depletion", "medium"),
        ("Ecosystem", "ˈiːkoʊsɪstəm", "A biological community of interacting organisms and their physical environment.", "Coral reefs represent one of the most fragile marine ecosystems on Earth.", "habitat, biological community", "", "easy"),
        ("Conservation", "ˌkɑːnsərˈveɪʃən", "The prevention of the wasteful use of a resource; preservation and protection of wildlife.", "Wildlife conservation groups established a sanctuary for endangered rhinos.", "preservation, protection", "destruction", "medium"),
        ("Deforestation", "diːˌfɔːrɪˈsteɪʃən", "The action of clearing a wide area of trees.", "Deforestation contributes significantly to greenhouse gas emissions.", "logging, tree removal", "afforestation, reforestation", "medium"),
        ("Pollutant", "pəˈluːtənt", "A substance that pollutes something, especially water or the atmosphere.", "Factory emissions release hazardous chemical pollutants into the air.", "contaminant, waste", "", "easy"),
        ("Renewable", "rɪˈnuːəbl", "Capable of being replenished naturally with the passage of time.", "Wind and solar are clean, renewable sources of electrical energy.", "sustainable, inexhaustible", "non-renewable, finite", "easy"),
        ("Emission", "iˈmɪʃən", "The production and discharge of something, especially gas or radiation.", "Electric vehicles produce zero direct tailpipe carbon emissions.", "discharge, release", "absorption", "medium"),
        ("Habitat", "ˈhæbɪtæt", "The natural home or environment of an animal, plant, or other organism.", "The arctic tundra provides a natural habitat for polar bears.", "environment, territory", "", "easy"),
        ("Extinction", "ɪkˈstɪŋkʃən", "The state or process of a species, family, or larger group being or becoming extinct.", "Poaching and habitat loss push many majestic predators close to extinction.", "destruction, eradication", "survival", "medium"),
        ("Climate", "ˈklaɪmət", "The weather conditions prevailing in an area in general or over a long period.", "Rising sea levels are a direct consequence of global climate change.", "weather pattern", "", "easy"),
        ("Drought", "draʊt", "A prolonged period of abnormally low rainfall, leading to a shortage of water.", "The severe drought caused devastating crop failures across the region.", "dry spell, aridity", "flood, deluge", "medium"),
        ("Glacier", "ˈɡleɪʃər", "A slowly moving mass or river of ice formed by the accumulation of snow.", "Rising global temperatures cause polar glaciers to melt at alarming rates.", "ice sheet", "", "easy"),
        ("Organic", "ɔːrˈɡænɪk", "Produced without using artificial chemical fertilizers or pesticides.", "Many farmers have transitioned to organic agricultural practices.", "natural, eco-friendly", "synthetic, chemical", "easy"),
        ("Recycle", "ˌriːˈsaɪkl", "Convert waste into reusable material.", "Cities encourage residents to recycle plastic bottles, aluminum cans, and paper.", "reprocess, reuse", "discard, waste", "easy"),
        ("Sanctuary", "ˈsæŋktʃueri", "A place of safety; a nature reserve where animals are protected.", "The bird sanctuary protects thousands of migratory species each winter.", "refuge, reserve", "", "medium"),
        ("Fossil Fuel", "ˈfɑːsl fjuːəl", "A natural fuel such as coal or gas, formed in the geological past from the remains of living organisms.", "Transitioning away from fossil fuel combustion is vital for cleaner skies.", "non-renewable energy", "", "easy"),
        ("Ozone Layer", "ˈoʊzoʊn ˌleɪər", "A layer in the earth's stratosphere that absorbs most of the ultraviolet radiation reaching the earth.", "The Montreal Protocol successfully helped the ozone layer recover.", "protective atmospheric layer", "", "medium"),
        ("Reforestation", "ˌriːˌfɔːrɪˈsteɪʃən", "The process of replanting an area with trees.", "Community volunteers planted thousands of saplings for the reforestation project.", "tree planting", "deforestation", "medium"),
        ("Pristine", "ˈprɪstiːn", "In its original condition; unspoiled.", "The deep mountain lake remained crystal clear and completely pristine.", "untouched, unspoiled", "polluted, contaminated", "hard"),
        ("Precipitation", "prɪˌsɪpɪˈteɪʃən", "Rain, snow, sleet, or hail that falls to or condenses on the ground.", "Tropical rainforests receive heavy annual precipitation.", "rainfall, snowfall", "drought", "hard"),
        ("Compost", "ˈkɑːmpoʊst", "Decayed organic material used as a plant fertilizer.", "Gardeners use food scraps and dried leaves to create rich compost.", "organic fertilizer, mulch", "", "easy"),
        ("Contaminate", "kənˈtæmɪneɪt", "Make something impure by exposure to or addition of a poisonous or polluting substance.", "Industrial runoff threatened to contaminate the municipal drinking water supply.", "pollute, taint", "purify, cleanse", "medium"),
        ("Endangered", "ɪnˈdeɪndʒərd", "At serious risk of extinction.", "Sea turtles are strictly protected endangered animals worldwide.", "threatened, vulnerable", "abundant, thriving", "easy"),
        ("Geothermal", "ˌdʒiːoʊˈθɜːrml", "Relating to or produced by the internal heat of the earth.", "Iceland generates most of its electricity from clean geothermal power.", "earth-heat energy", "", "hard"),
        ("Greenhouse Effect", "ˈɡriːnhaʊs ɪˌfekt", "The trapping of the sun's warmth in a planet's lower atmosphere.", "Excess greenhouse gas emissions intensify the global greenhouse effect.", "global warming mechanism", "", "medium"),
        ("Flora", "ˈflɔːrə", "The plants of a particular region, habitat, or geological period.", "The desert flora consists primarily of hardy cacti and drought-resistant shrubs.", "plant life, vegetation", "fauna", "medium"),
        ("Fauna", "ˈfɔːnə", "The animals of a particular region, habitat, or geological period.", "Australia is famous for its unique native fauna, including kangaroos and koalas.", "animal life, wildlife", "flora", "medium"),
        ("Poaching", "ˈpoʊtʃɪŋ", "Illegal hunting or capturing of wild animals.", "Park rangers patrol the national park day and night to stop elephant poaching.", "illegal hunting", "", "medium"),
        ("Erosion", "ɪˈroʊʒən", "The process of eroding or being eroded by wind, water, or other natural agents.", "Planting deep-rooted grasses along coastal sand dunes helps prevent soil erosion.", "wearing away, degradation", "", "medium"),
        ("Toxic", "ˈtɑːksɪk", "Poisonous, harmful, or deadly.", "Proper disposal prevents toxic chemicals from seeping into underground aquifers.", "poisonous, venomous", "non-toxic, harmless", "easy"),
        ("Wilderness", "ˈwɪldərnəs", "An uncultivated, uninhabited, and inhospitable region.", "Hikers must carry essential survival gear when exploring the northern wilderness.", "backcountry, wilds", "city, civilization", "easy"),
        ("Solar Panel", "ˈsoʊlər ˌpænl", "A panel designed to absorb the sun's rays as a source of energy for generating electricity.", "Installing rooftop solar panels lowers domestic electricity bills.", "photovoltaic cell", "", "easy"),
        ("Acid Rain", "ˈæsɪd reɪn", "Rainfall made sufficiently acidic by atmospheric pollution that it causes environmental harm.", "Stricter sulfur dioxide regulations successfully reduced incidents of acid rain.", "acidic precipitation", "", "medium"),
        ("Reservoir", "ˈrezərvwɑːr", "A large natural or artificial lake used as a source of water supply.", "The city's main reservoir reached ninety percent capacity after spring rains.", "lake, water basin", "", "medium")
    ],
    "Communication & Media": [
        ("Broadcast", "ˈbrɔːdkæst", "Transmit a program or some information by radio or television.", "The evening news is broadcast live at seven o'clock every night.", "telecast, transmit", "", "easy"),
        ("Journalism", "ˈdʒɜːrnəlɪzəm", "The activity or profession of writing for newspapers, magazines, or news websites.", "Investigative journalism plays a vital role in holding authorities accountable.", "reporting, press", "", "medium"),
        ("Correspondent", "ˌkɔːrəˈspɑːndənt", "A person who writes letters or news reports to a newspaper, magazine, or broadcasting organization.", "The war correspondent reported from the frontline under dangerous conditions.", "reporter, journalist", "", "hard"),
        ("Press Release", "ˈpres rɪˌliːs", "An official statement issued to newspapers giving information on a particular matter.", "The tech firm issued a press release announcing its new product launch.", "official statement", "", "medium"),
        ("Editorial", "ˌedɪˈtɔːriəl", "A newspaper article written by or on behalf of an editor that gives an opinion.", "The Sunday newspaper published a compelling editorial on public transport.", "opinion piece, commentary", "", "medium"),
        ("Sensationalism", "senˈseɪʃənəlɪzəm", "The use of exciting or shocking stories or language at the expense of accuracy.", "Tabloids frequently rely on sensationalism to boost their readership.", "exaggeration, yellow journalism", "objectivity", "hard"),
        ("Censorship", "ˈsensərʃɪp", "The suppression or prohibition of any parts of books, films, or news considered obscene or politically unacceptable.", "Free speech advocates actively campaign against government censorship.", "suppression, restriction", "free expression", "hard"),
        ("Misinformation", "ˌmɪsɪnfərˈmeɪʃən", "False or inaccurate information, especially that which is deliberately intended to deceive.", "Social media platforms have instituted fact-checking tools to combat misinformation.", "fake news, disinformation", "truth, facts", "medium"),
        ("Viral", "ˈvaɪrəl", "Relating to or involving an image, video, piece of information, etc., that is circulated rapidly on the internet.", "Her heartwarming rescue video went viral and gained ten million views in one day.", "widespread, trending", "", "easy"),
        ("Podcast", "ˈpɑːdkæst", "A digital audio file made available on the internet for downloading to a computer or mobile device.", "I listen to an educational science podcast during my daily commute.", "audio show", "", "easy"),
        ("Headline", "ˈhedlaɪn", "A heading at the top of an article or page in a newspaper or magazine.", "The bold front-page headline captured the nation's attention.", "heading, title", "", "easy"),
        ("Subscriber", "səbˈskraɪbər", "A person who receives a publication or service regularly by paying in advance.", "The channel celebrated reaching one million YouTube subscribers.", "member, follower", "", "easy"),
        ("Columnist", "ˈkɑːləmnɪst", "A journalist contributing regularly to a newspaper or magazine.", "The financial columnist provided practical budgeting advice for young families.", "writer, commentator", "", "medium"),
        ("Interview", "ˈɪntərvjuː", "A meeting of people face to face, especially for consultation or assessment.", "The journalist conducted an exclusive interview with the acclaimed author.", "meeting, consultation", "", "easy"),
        ("Media Literacy", "ˈmiːdiə ˈlɪtərəsi", "The ability to critically analyze messages in all media formats.", "Teaching media literacy empowers students to identify biased reporting.", "critical awareness", "", "medium"),
        ("Dialogue", "ˈdaɪəlɔːɡ", "Conversation between two or more people as a feature of a book, play, or film.", "Constructive diplomatic dialogue resolved the border disagreement peacefully.", "conversation, discussion", "monologue", "easy"),
        ("Convey", "kənˈveɪ", "Make an idea, impression, or feeling known or understandable to someone.", "Clear body language and eye contact help convey confidence.", "communicate, express", "hide, conceal", "medium"),
        ("Articulate", "ɑːrˈtɪkjuleɪt", "Having or showing the ability to speak fluently and coherently.", "She is an articulate speaker who explains complex concepts with ease.", "eloquent, clear", "inarticulate, unclear", "hard"),
        ("Persuasion", "pərˈsweɪʒən", "The action or fact of persuading someone or of being persuaded to do or believe something.", "Effective advertising relies on subtle psychological persuasion.", "influence, convincing", "dissuasion", "medium"),
        ("Rhetoric", "ˈretərɪk", "The art of effective or persuasive speaking or writing.", "The politician's persuasive rhetoric resonated with young voters across the country.", "eloquence, oratory", "", "hard"),
        ("Ambiguous", "æmˈbɪɡjuəs", "Open to more than one interpretation; having a double meaning.", "The contract's wording was ambiguous and caused confusion between partners.", "unclear, vague", "clear, explicit", "hard"),
        ("Eloquent", "ˈeləkwənt", "Fluent or persuasive in speaking or writing.", "The defense attorney delivered an eloquent closing argument to the jury.", "expressive, persuasive", "clumsy, tongue-tied", "medium"),
        ("Disclose", "dɪsˈkloʊz", "Make secret or new information known.", "The whistleblower chose to disclose the company's unauthorized data collection.", "reveal, expose", "conceal, hide", "medium"),
        ("Disclaimer", "dɪsˈkleɪmər", "A statement that denies something, especially responsibility.", "The financial video begins with a disclaimer stating it is not formal investment advice.", "denial, notice", "", "medium"),
        ("Praise", "preɪz", "Express warm approval or admiration of.", "The film critic gave high praise to the director's visual storytelling.", "compliment, commendation", "criticism, blame", "easy"),
        ("Criticism", "ˈkrɪtɪsɪzəm", "The expression of disapproval of someone or something based on perceived faults or mistakes.", "Constructive criticism helps creative writers polish their manuscripts.", "critique, disapproval", "praise, praise", "easy"),
        ("Engagement", "ɪnˈɡeɪdʒmənt", "The amount of interaction, such as comments, shares, or likes, that content receives.", "Interactive polls significantly boost user engagement on community forums.", "interaction, involvement", "disinterest", "medium"),
        ("Caption", "ˈkæpʃən", "A title or brief explanation appended to an illustration, cartoon, or poster.", "Read the image caption below for details on the historical photo.", "description, subtitle", "", "easy"),
        ("Influencer", "ˈɪnfluənsər", "A person with the ability to influence potential buyers by promoting or recommending items on social media.", "Brands collaborate with social media influencers to reach teenage audiences.", "creator, trendsetter", "", "easy"),
        ("Subtle", "ˈsʌtl", "So delicate or precise as to be difficult to analyze or describe.", "There was a subtle change in tone during the second half of the speech.", "understated, fine", "obvious, blatant", "medium"),
        ("Platitude", "ˈplætɪtuːd", "A remark or statement, especially one with a moral content, that has been used too often to be interesting.", "The commencement speaker avoided meaningless platitudes and shared genuine experiences.", "cliche, truism", "original thought", "hard"),
        ("Coherent", "koʊˈhɪrənt", "Logical and consistent in thought or speech.", "She presented a coherent argument that convinced the review board.", "logical, reasoned", "incoherent, disjointed", "hard"),
        ("Jargon", "ˈdʒɑːrɡən", "Special words or expressions that are used by a particular profession or group.", "The manual avoids medical jargon so that patients can easily follow the steps.", "technical terms, slang", "plain English", "medium"),
        ("Empathy", "ˈempəθi", "The ability to understand and share the feelings of another.", "Active listening requires deep empathy and patience without judgment.", "understanding, compassion", "apathy, coldness", "easy"),
        ("Transparency", "trænsˈpærənsi", "The condition of being easy to perceive or detect; openness and honesty in communication.", "The government promised full transparency regarding public budget expenditures.", "openness, honesty", "secrecy, opacity", "medium")
    ],
    "Jobs & Careers": [
        ("Applicant", "ˈæplɪkənt", "A person who makes a formal application for something, especially a job.", "Over two hundred applicants applied for the senior software engineer position.", "candidate, jobseeker", "", "easy"),
        ("Resume", "ˈrezəmeɪ", "A brief account of a person's education, qualifications, and previous experience, typically sent with a job application.", "She highlighted her project leadership skills on her one-page resume.", "CV, curriculum vitae", "", "easy"),
        ("Promotion", "prəˈmoʊʃən", "Activity that supports or provides active encouragement for the furtherance of a cause, venture, or aim; advancement.", "Hard work and dedication earned him a promotion to regional sales director.", "advancement, upgrade", "demotion", "easy"),
        ("Probation", "proʊˈbeɪʃən", "A period of trial in which a newly recruited employee's fitness for the job is tested.", "New hires undergo a ninety-day probation period before receiving full benefits.", "trial period, evaluation", "permanent tenure", "medium"),
        ("Headhunter", "ˈhedhʌntər", "A recruiter of personnel, especially of executive staff, for a corporation.", "A corporate headhunter contacted her regarding an executive role at a rival firm.", "recruiter, scout", "", "medium"),
        ("Qualification", "ˌkwɑːlɪfɪˈkeɪʃən", "A pass of an examination or an official completion of a course.", "Fluency in two foreign languages is a mandatory qualification for the diplomatic post.", "credential, eligibility", "", "medium"),
        ("Vocation", "voʊˈkeɪʃən", "A strong feeling of suitability for a particular career or occupation.", "Nursing was not just a job for her; it was a deeply rewarding lifelong vocation.", "calling, profession", "", "hard"),
        ("Remuneration", "rɪˌmjuːnəˈreɪʃən", "Money paid for work or a service.", "The executive package includes a competitive base salary and attractive stock remuneration.", "compensation, payment", "", "hard"),
        ("Apprenticeship", "əˈprentɪsʃɪp", "The position of an apprentice who learns a trade from a skilled employer.", "He completed a four-year plumbing apprenticeship before launching his own company.", "training, internship", "", "medium"),
        ("Telecommute", "ˈtelɪkəmjuːt", "Work from home, making use of the internet, email, and the telephone.", "Many tech companies allow staff to telecommute three days a week.", "work remotely, WFH", "work on-site", "medium"),
        ("Appraisal", "əˈpreɪzəl", "An assessment or evaluation of an employee's job performance.", "Her annual appraisal praised her problem-solving abilities and punctual delivery.", "review, evaluation", "", "hard"),
        ("Overtime", "ˈoʊvərtaɪm", "Time worked in addition to one's normal working hours.", "Employees receive time-and-a-half pay whenever they work overtime on weekends.", "extra hours", "", "easy"),
        ("Severance", "ˈsevərəns", "An amount paid to an employee on the early termination of an agreement.", "Laid-off workers received three months of severance pay and healthcare coverage.", "separation pay", "", "hard"),
        ("Freelancer", "ˈfriːlænsər", "A person who works independently on a contract basis rather than being employed by a company.", "As a graphic design freelancer, she sets her own working schedule.", "contractor, independent", "full-time employee", "easy"),
        ("Resignation", "ˌrezɪɡˈneɪʃən", "An act of retiring or giving up a position.", "The CEO submitted his formal resignation to the board of directors.", "departure, stepping down", "appointment", "medium"),
        ("Cover Letter", "ˈkʌvər ˌletər", "A letter sent with, and explaining the contents of, another document (e.g. a resume).", "Write a personalized cover letter explaining why you are ideal for the position.", "application letter", "", "easy"),
        ("Interview", "ˈɪntərvjuː", "A formal meeting in which one or more persons question an applicant.", "She dressed professionally and arrived early for the job interview.", "screening, meeting", "", "easy"),
        ("Onboarding", "ˈɑːnbɔːrdɪŋ", "The action or process of integrating a new employee into an organization.", "The company's two-week onboarding program introduces company values and tools.", "orientation, training", "offboarding", "medium"),
        ("Seniority", "siːˈnjɔːrəti", "The fact or state of being older or higher in position or status than someone else.", "Shift allocations are often determined according to employee seniority.", "rank, priority", "juniority", "medium"),
        ("Pension", "ˈpenʃən", "A regular payment made during a person's retirement from an investment fund.", "Teachers in the public school district contribute to a state pension plan.", "retirement fund", "", "medium"),
        ("Perk", "pɜːrk", "An advantage or benefit following from a job or a situation.", "Free gourmet lunches and gym memberships are popular employee perks.", "benefit, advantage", "", "easy"),
        ("Blue-collar", "ˈbluː kɑːlər", "Relating to manual work or workers, particularly in industry.", "Factory technicians and construction workers are essential blue-collar professionals.", "manual, industrial", "white-collar", "easy"),
        ("White-collar", "ˈwaɪt kɑːlər", "Relating to the work done by people who work in an office or other professional environment.", "The city's financial district employs thousands of white-collar professionals.", "office-based, professional", "blue-collar", "easy"),
        ("Workaholic", "ˌwɜːrkəˈhɑːlɪk", "A person who compulsively works excessively hard and long hours.", "He is a self-confessed workaholic who rarely takes weekend breaks.", "over-worker", "slacker", "easy"),
        ("Careerist", "kəˈrɪrɪst", "A person who regards their career as the most important thing in life.", "Her ambition as a careerist motivated her rapid rise up the corporate ladder.", "climber", "", "hard"),
        ("Compensation", "ˌkɑːmpenˈseɪʃən", "The money received by an employee from an employer as a salary or wages.", "The total compensation package includes health insurance and annual stock options.", "remuneration, pay", "", "medium"),
        ("Redundancy", "rɪˈdʌndənsi", "The state of being no longer in employment because there is no more work available.", "Automation resulted in the redundancy of fifty assembly line positions.", "layoff, job loss", "hiring", "hard"),
        ("Climb the ladder", "klaɪm ðə ˈlædər", "Make progress in one's career or rise through the ranks of an organization.", "Mentorship and steady performance helped her climb the corporate ladder quickly.", "advance, succeed", "", "medium"),
        ("Tenure", "ˈtenjər", "Guaranteed permanent employment, especially as a teacher or professor.", "After publishing landmark research, the professor was granted academic tenure.", "permanence, status", "probation", "hard"),
        ("Recruiter", "rɪˈkruːtər", "A person whose job is to enlist or find new personnel for an organization.", "The tech recruiter reached out on LinkedIn regarding an exciting frontend opening.", "talent scout, hiring agent", "", "easy"),
        ("Portfolio", "pɔːrtˈfoʊlioʊ", "A collection of drawings, documents, etc. that represent a person's work.", "Her UI/UX portfolio showcases mobile application prototypes.", "showcase, sample work", "", "easy"),
        ("Discretionary", "dɪˈskreʃəneri", "Available for use at the discretion of the user; not fixed by a predetermined rule.", "The manager awarded a discretionary bonus to outstanding project contributors.", "optional, flexible", "mandatory", "hard"),
        ("Moonlighting", "ˈmuːnlaɪtɪŋ", "Having a second job in addition to one's regular employment.", "He spent evenings moonlighting as an online English tutor.", "second job", "", "medium"),
        ("Grievance", "ˈɡriːvəns", "A real or imagined wrong or other cause for complaint or protest.", "Employees may submit a workplace grievance directly to human resources.", "complaint, dispute", "", "hard"),
        ("Stipend", "ˈstaɪpend", "A fixed regular sum paid as a salary or as an allowance to a student or trainee.", "Graduate research assistants receive a monthly living stipend from the lab.", "allowance, grant", "", "medium")
    ],
    "Shopping & Commerce": [
        ("Receipt", "rɪˈsiːt", "A written acknowledgment of having received a specified amount of money or goods.", "Keep your purchase receipt in case you wish to return the jacket.", "proof of purchase, bill", "", "easy"),
        ("Refund", "ˈriːfʌnd", "A repayment of a sum of money, typically to a dissatisfied customer.", "The store provided a full refund when the electronic gadget proved defective.", "reimbursement, return", "", "easy"),
        ("Bargain", "ˈbɑːrɡən", "A thing bought or offered for sale more cheaply than is usual or expected.", "At fifty percent off, this designer coat was an incredible bargain.", "deal, discount", "rip-off", "easy"),
        ("Wholesale", "ˈhoʊlseɪl", "The selling of goods in large quantities to be retailed by others.", "Supermarkets purchase fresh produce at wholesale prices from local farmers.", "bulk sale", "retail", "medium"),
        ("Retail", "ˈriːteɪl", "The sale of goods to the public in relatively small quantities for use or consumption.", "Online retail sales grew rapidly over the holiday shopping season.", "consumer sales", "wholesale", "easy"),
        ("Warranty", "ˈwɔːrənti", "A written guarantee, issued to the purchaser of an article by its manufacturer.", "The laptop comes with a two-year manufacturer warranty against hardware faults.", "guarantee, protection plan", "", "medium"),
        ("Transaction", "trænˈzækʃən", "An instance of buying or selling something; a business deal.", "Contactless transactions allow shoppers to pay quickly using their smartphones.", "deal, purchase", "", "easy"),
        ("Invoice", "ˈɪnvɔɪs", "A list of goods sent or services provided, with a statement of the sum due.", "The freelance consultant sent an itemized invoice for twenty billable hours.", "bill, statement", "", "medium"),
        ("Merchant", "ˈmɜːrtʃənt", "A person or company involved in wholesale trade, especially one dealing with foreign countries.", "Local wine merchants imported authentic vintages from Bordeaux.", "trader, seller", "buyer", "medium"),
        ("Inventory", "ˈɪnvəntɔːri", "A complete list of items such as property, goods in stock, or the contents of a building.", "The retail store conducts a quarterly inventory check to count remaining stock.", "stock, supplies", "", "medium"),
        ("Counterfeit", "ˈkaʊntərfɪt", "Made in exact imitation of something valuable with the intention to deceive.", "Customs officials seized thousands of counterfeit luxury handbags at the port.", "fake, forged", "genuine, authentic", "hard"),
        ("Authentic", "ɔːˈθentɪk", "Of undisputed origin; genuine.", "The vintage boutique certifies that every leather item is one hundred percent authentic.", "genuine, real", "counterfeit, fake", "medium"),
        ("Discount", "ˈdɪskaʊnt", "A deduction from the usual cost of something.", "Students and seniors receive a ten percent discount on all book purchases.", "reduction, markdown", "surcharge, markup", "easy"),
        ("Clearance", "ˈklɪrəns", "The sale of goods at reduced prices in order to get rid of surplus stock.", "We bought winter coats at the end-of-season clearance sale.", "liquidation, markdown", "", "easy"),
        ("Customer", "ˈkʌstəmər", "A person or organization that buys goods or services from a store or business.", "Satisfied customers often recommend our bakery to their friends.", "shopper, buyer", "seller", "easy"),
        ("Aisle", "aɪl", "A passage between rows of seats or shelves in a supermarket or church.", "You can find breakfast cereals and pancake mix in aisle four.", "hallway, walkway", "", "easy"),
        ("Cashier", "kæˈʃɪr", "A person handling payments and receipts in a shop, bank, or other business.", "The cashier scanned my items and handed me the printed receipt.", "teller, clerk", "", "easy"),
        ("Voucher", "ˈvaʊtʃər", "A small printed piece of paper that entitles the holder to a discount or that may be exchanged for goods.", "She redeemed a twenty-dollar gift voucher toward new running shoes.", "coupon, token", "", "easy"),
        ("Defective", "dɪˈfektɪv", "Imperfect or faulty.", "Return the defective toaster to the customer service counter for a replacement.", "flawed, broken", "flawless, intact", "medium"),
        ("Expiry Date", "ɪkˈspaɪəri deɪt", "The date after which something is no longer valid or safe to consume.", "Always check the expiry date on dairy products before buying.", "use-by date", "", "easy"),
        ("Impulse Buying", "ˈɪmpʌls ˌbaɪɪŋ", "The buying of goods without planning to do so in advance, as a result of a sudden whim.", "Placing candy near checkout counters encourages impulse buying.", "spontaneous purchase", "planned shopping", "medium"),
        ("Consumerism", "kənˈsuːmərɪzəm", "The protection or promotion of the interests of consumers; the preoccupation with the acquisition of goods.", "Critics argue that excessive consumerism produces unnecessary plastic waste.", "materialism", "frugality", "hard"),
        ("Loyalty Program", "ˈlɔɪəlti ˌproʊɡræm", "A rewards program offered by a company to customers who frequently make purchases.", "Join the airline's loyalty program to earn reward miles on every flight.", "rewards program", "", "medium"),
        ("E-commerce", "ˈiː kɑːmɜːrs", "Commercial transactions conducted electronically on the internet.", "The rise of e-commerce transformed how people shop for clothing and electronics.", "online shopping", "brick-and-mortar", "easy"),
        ("Shopping Cart", "ˈʃɑːpɪŋ kɑːrt", "A bag or wheeled cart provided by a store for holding merchandise selected by a customer.", "He filled his shopping cart with fresh vegetables, milk, and bread.", "trolley", "", "easy"),
        ("Exchange", "ɪksˈtʃeɪndʒ", "An act of giving one thing and receiving another in return.", "If the shirt does not fit, you can exchange it for a larger size.", "swap, trade", "", "easy"),
        ("Pricey", "ˈpraɪsi", "Expensive.", "Dining at five-star rooftop restaurants can be quite pricey.", "costly, expensive", "cheap, affordable", "easy"),
        ("Affordable", "əˈfɔːrdəbl", "Inexpensive; reasonably priced.", "The brand is known for offering stylish yet affordable clothing for students.", "economical, reasonable", "expensive, pricey", "easy"),
        ("Rip-off", "ˈrɪp ɔːf", "A fraud or swindle, especially something that is grossly overpriced.", "Ten dollars for a bottle of plain water at the festival is a total rip-off.", "overpriced scam", "bargain", "medium"),
        ("Bulk", "bʌlk", "The mass or magnitude of something large; in large quantity.", "Buying toilet paper and rice in bulk saves money over time.", "large volume", "small quantity", "medium"),
        ("Shoplifting", "ˈʃɑːplɪftɪŋ", "The action of stealing goods from a shop while pretending to be a customer.", "Security cameras and alarms are installed to prevent shoplifting.", "theft, stealing", "", "medium"),
        ("Splurge", "splɜːrdʒ", "An act of spending money freely or extravagantly.", "She decided to splurge on a luxurious spa weekend after completing her exams.", "treat oneself, spend lavishly", "save, pinch pennies", "medium"),
        ("Vendor", "ˈvendər", "A person or company offering something for sale.", "Street food vendors served hot noodles to late-night commuters.", "seller, merchant", "buyer", "easy"),
        ("Checkout", "ˈtʃekaʊt", "A point at which goods are paid for in a supermarket or other store.", "Self-service checkout lanes reduce waiting times during busy hours.", "register, till", "", "easy"),
        ("Window Shopping", "ˈwɪndoʊ ˌʃɑːpɪŋ", "The activity of looking at the goods in shop windows in without intending to buy anything.", "We spent Sunday afternoon window shopping along Fifth Avenue.", "browsing", "", "easy")
    ],
    "Transportation & Commute": [
        ("Transit", "ˈtrænzɪt", "The carrying of people or things from one place to another; public transportation.", "The city invested in rapid light-rail transit to reduce highway congestion.", "transportation, conveyance", "", "medium"),
        ("Congestion", "kənˈdʒestʃən", "The state of being congested, especially with traffic.", "Rush hour causes severe traffic congestion on the main suspension bridge.", "traffic jam, gridlock", "clear road", "medium"),
        ("Fare", "fer", "The money a passenger on public transportation has to pay.", "Bus fare can be paid using a contactless smart card.", "ticket price, fee", "", "easy"),
        ("Pedestrian", "pəˈdestriən", "A person walking along a road or in a developed area.", "Cars must yield to pedestrians waiting at marked crosswalks.", "walker, foot-traveler", "driver, motorist", "easy"),
        ("Intersection", "ˌɪntərˈsekʃən", "A point at which two or more roads intersect.", "Slow down and watch for turning vehicles at the busy intersection.", "crossroads, junction", "", "easy"),
        ("Gridlock", "ˈɡrɪdlɑːk", "A traffic jam affecting a whole network of intersecting streets.", "A stalled truck caused total gridlock in the downtown financial district.", "traffic jam, standstill", "free flow", "medium"),
        ("Carpool", "ˈkɑːrpuːl", "An arrangement between people to make a regular journey in a single vehicle.", "Coworkers organized a carpool to save on fuel and toll charges.", "rideshare", "drive solo", "easy"),
        ("Toll", "toʊl", "A charge payable for permission to use a particular road or bridge.", "Drivers can pay the highway toll electronically without stopping.", "fee, charge", "", "easy"),
        ("Expressway", "ɪkˈspresweɪ", "A highway designed for fast traffic, with controlled entrance and exit points.", "The new expressway shortened travel time between the two cities to thirty minutes.", "highway, freeway", "local street", "easy"),
        ("Commuter", "kəˈmjuːtər", "A person who travels some distance to work on a regular basis.", "Subway trains are packed with morning commuters heading into the city center.", "passenger, worker", "", "easy"),
        ("Locomotive", "ˌloʊkəˈmoʊtɪv", "A powered rail vehicle used for pulling trains.", "The diesel locomotive pulled a twenty-car freight train across the plains.", "engine, train", "", "medium"),
        ("Roundabout", "ˈraʊndəbaʊt", "A road junction at which traffic moves in one direction around a central island.", "Traffic flows smoothly through the roundabout without need for traffic lights.", "traffic circle, rotary", "", "medium"),
        ("Crosswalk", "ˈkrɔːswɔːk", "A marked part of a road where pedestrians have right of way to cross.", "Always cross the avenue within the painted white lines of the crosswalk.", "pedestrian crossing", "", "easy"),
        ("Detour", "ˈdiːtʊr", "A long or roundabout route that is taken to avoid something or to visit somewhere along the way.", "Road construction forced drivers to take a five-mile detour through the countryside.", "diversion, bypass", "direct route", "easy"),
        ("Overpass", "ˈoʊvərpæs", "A bridge by which a road or railway line passes over another.", "The elevated highway overpass spans across the busy train tracks.", "flyover, bridge", "underpass", "easy"),
        ("Underpass", "ˈʌndərpæs", "A road or pedestrian tunnel passing under another road or railway.", "Pedestrians can safely cross the eight-lane highway through the lighted underpass.", "tunnel, subway", "overpass", "easy"),
        ("Subway", "ˈsʌbweɪ", "An underground electric railroad.", "Taking the subway is the fastest way to travel across Manhattan during rush hour.", "metro, underground", "", "easy"),
        ("Bicycle Lane", "ˈbaɪsɪkl leɪn", "A division of a road marked off with painted lines, for use by cyclists.", "The city added dedicated bicycle lanes to promote green commuting.", "bike path, cycle track", "", "easy"),
        ("Navigation", "ˌnævɪˈɡeɪʃən", "The process or activity of accurately ascertaining one's position and planning and following a route.", "GPS navigation apps provide real-time traffic updates and route changes.", "routing, map-reading", "", "medium"),
        ("Speedometer", "spiːˈdɑːmɪtər", "An instrument on a vehicle's dashboard indicating its speed.", "Keep an eye on the speedometer to avoid exceeding the posted speed limit.", "speed gauge", "", "easy"),
        ("Speed Limit", "ˈspiːd ˌlɪmɪt", "The maximum speed at which a vehicle may legally travel on a particular stretch of road.", "The speed limit on residential streets is twenty-five miles per hour.", "maximum legal speed", "", "easy"),
        ("Pavement", "ˈpeɪvmənt", "A hard surface path for pedestrians beside a road; sidewalk.", "Children rode their scooters safely on the wide concrete pavement.", "sidewalk, walkway", "roadway", "easy"),
        ("Overtake", "ˌoʊvərˈteɪk", "Catch up with and pass while travelling in the same direction.", "Check your rearview mirrors carefully before you overtake the slow-moving truck.", "pass, blow past", "trail, follow", "medium"),
        ("Yield", "jiːld", "Give way to arguments, demands, or traffic.", "Drivers approaching the roundabout must yield to traffic already circulating.", "give way, cede", "insist, proceed", "easy"),
        ("Terminal", "ˈtɜːrmɪnl", "A building where passengers embark or disembark from aircraft, trains, or other transport.", "International flights depart from Terminal 2 at the airport.", "station, concourse", "", "easy"),
        ("Shuttle", "ˈʃʌtl", "A vehicle that travels regularly between two places.", "A complimentary airport shuttle runs between the hotel and departures every twenty minutes.", "transfer bus", "", "easy"),
        ("Hitchhike", "ˈhɪtʃhaɪk", "Travel by getting free rides in passing vehicles.", "Backpackers occasionally hitchhike along scenic coastal highways.", "thumb a ride", "", "medium"),
        ("Ferry", "ˈferi", "A boat or ship for conveying passengers and goods, especially over a relatively short distance.", "We boarded the car ferry to cross the bay to the nearby island.", "boat, water taxi", "", "easy"),
        ("Carpool Lane", "ˈkɑːrpuːl leɪn", "A lane on a highway reserved for vehicles carrying two or more passengers.", "Using the carpool lane shaved twenty minutes off our morning commute.", "HOV lane", "", "medium"),
        ("Chauffeur", "ˈʃoʊfər", "A person employed to drive a private or rented automobile.", "The hotel provided a private chauffeur to escort VIP guests to the gala.", "driver", "", "hard"),
        ("Collision", "kəˈlɪʒən", "An instance of one moving object or person striking violently against another.", "The defensive driving course teaches techniques to prevent rear-end collisions.", "crash, accident", "", "medium"),
        ("Pothole", "ˈpɑːthoʊl", "A deep depression or hollow in a road surface, caused by wear or subsidence.", "Winter freezing and thawing caused several large potholes along the avenue.", "rut, road crater", "", "easy"),
        ("Jaywalking", "ˈdʒeɪwɔːkɪŋ", "Crossing or walking in the street unlawfully or without regard for approaching traffic.", "Police officers issued warnings for dangerous jaywalking on busy avenues.", "illegal road crossing", "", "medium"),
        ("Fleet", "fliːt", "A group of motor vehicles, aircraft, or ships owned or operated by a single company.", "The delivery company converted its entire delivery fleet to electric vans.", "group of vehicles", "", "medium"),
        ("Commutation", "ˌkɑːmjuːˈteɪʃən", "The action of commuting or regular travel between home and work.", "The city offered subsidized rail tickets to encourage daily commutation by train.", "regular commute", "", "hard")
    ],
    "Academic English": [
        ("Hypothesis", "haɪˈpɑːθəsɪs", "A proposed explanation made on the basis of limited evidence as a starting point for further investigation.", "Scientists formulated a testable hypothesis regarding cellular aging.", "theory, premise", "proven fact", "medium"),
        ("Methodology", "ˌmeθəˈdɑːlədʒi", "A system of methods used in a particular area of study or activity.", "The research paper outlines a rigorous qualitative methodology for data collection.", "approach, procedure", "", "hard"),
        ("Empirical", "ɪmˈpɪrɪkl", "Based on, concerned with, or verifiable by observation or experience rather than theory or pure logic.", "The findings are backed by empirical evidence gathered from clinical trials.", "observed, experiential", "theoretical, speculative", "hard"),
        ("Correlation", "ˌkɔːrəˈleɪʃən", "A mutual relationship or connection between two or more things.", "Researchers discovered a positive correlation between exercise and mental well-being.", "relationship, link", "independence", "medium"),
        ("Causation", "kɔːˈzeɪʃən", "The action of causing something; the relationship between cause and effect.", "Statistical correlation does not necessarily imply direct causation.", "cause and effect", "", "medium"),
        ("Paradigm", "ˈpærədaɪm", "A typical example or pattern of something; a model or overarching framework.", "The discovery of quantum mechanics represented a fundamental paradigm shift in modern physics.", "model, framework", "", "hard"),
        ("Qualitative", "ˈkwɑːlɪteɪtɪv", "Relating to, measuring, or measured by the quality of something rather than its quantity.", "Qualitative research includes in-depth interviews and focus group discussions.", "descriptive", "quantitative", "medium"),
        ("Quantitative", "ˈkwɑːntɪteɪtɪv", "Relating to, measuring, or measured by the quantity of something rather than its quality.", "Quantitative analysis involved statistical processing of survey responses from ten thousand participants.", "numerical, statistical", "qualitative", "medium"),
        ("Peer-reviewed", "ˈpɪr rɪˌvjuːd", "Evaluated by other people in the same field before publication.", "Scientists submit their discovery manuscripts to peer-reviewed academic journals.", "refereed, validated", "unverified", "medium"),
        ("Citation", "saɪˈteɪʃən", "A quotation from or reference to a book, paper, or author, especially in a scholarly work.", "Proper academic citation prevents accidental plagiarism in research papers.", "reference, source credit", "", "easy"),
        ("Abstract", "ˈæbstrækt", "A summary of the contents of a book, article, or formal speech.", "The paper begins with a two-hundred-word abstract summarizing methods and conclusions.", "summary, synopsis", "full text", "easy"),
        ("Syntax", "ˈsɪntæks", "The arrangement of words and phrases to create well-formed sentences in a language.", "Grammatical syntax rules govern how clauses connect in formal writing.", "structure, grammar rules", "", "medium"),
        ("Phenomenon", "fəˈnɑːmɪnɑːn", "A fact or situation that is observed to exist or happen, especially one whose cause is in question.", "Aurora borealis is a magnificent atmospheric phenomenon seen in northern latitudes.", "occurrence, event", "", "medium"),
        ("Theoretical", "ˌθiːəˈretɪkl", "Concerned with or involving the theory of a subject or area of study rather than its practical application.", "Theoretical physics explores mathematical models of the cosmos.", "conceptual, abstract", "practical, applied", "medium"),
        ("Implication", "ˌɪmplɪˈkeɪʃən", "The conclusion that can be drawn from something although it is not explicitly stated.", "The study discusses the economic implications of clean energy subsidies.", "consequence, ramification", "", "medium"),
        ("Prerequisite", "priːˈrekwəzɪt", "A thing that is required as a prior condition for something else.", "A solid understanding of linear algebra is a prerequisite for machine learning.", "requirement, precondition", "", "hard"),
        ("Ubiquitous", "juːˈbɪkwɪtəs", "Present, appearing, or found everywhere.", "Smartphones have become ubiquitous in modern everyday life.", "omnipresent, everywhere", "rare, scarce", "hard"),
        ("Juxtaposition", "ˌdʒʌkstəpəˈzɪʃən", "The fact of two things being seen or placed close together with contrasting effect.", "The essay examines the dramatic juxtaposition of wealth and poverty in nineteenth-century London.", "contrast, comparison", "", "hard"),
        ("Synthesis", "ˈsɪnθəsɪs", "The combination of ideas to form a theory or system.", "Her literature review provides a masterful synthesis of fifty years of research.", "combination, integration", "separation, analysis", "hard"),
        ("Dichotomy", "daɪˈkɑːtəmi", "A division or contrast between two things that are or are represented as being opposed or entirely different.", "Philosophers debate the dichotomy between nature and nurture in human behavior.", "division, contrast", "unity", "hard"),
        ("Validity", "vəˈlɪdəti", "The quality of being logically or factually sound; soundness or cogency.", "Statistical tests confirmed the internal validity of the experimental results.", "soundness, legitimacy", "invalidity, flaw", "medium"),
        ("Variable", "ˈveriəbl", "An element, feature, or factor that is liable to vary or change.", "Temperature was maintained as the controlled variable throughout the experiment.", "factor, parameter", "constant", "easy"),
        ("Epistemology", "ɪˌpɪstəˈmɑːlədʒi", "The theory of knowledge, especially with regard to its methods, validity, and scope.", "Epistemology investigates how humans distinguish true belief from opinion.", "theory of knowledge", "", "hard"),
        ("Extrapolate", "ɪkˈstræpəleɪt", "Extend the application of a method or conclusion to an unknown situation by assuming existing trends will continue.", "Economists extrapolated future consumer spending based on quarterly retail data.", "project, infer", "", "hard"),
        ("Discourse", "ˈdɪskɔːrs", "Written or spoken communication or debate.", "Academic discourse on artificial intelligence ethics has intensified in recent years.", "dialogue, discussion", "", "hard"),
        ("Pedagogical", "ˌpedəˈɡɑːdʒɪkl", "Relating to teaching or education.", "The professor implemented innovative pedagogical techniques to engage students.", "educational, instructional", "", "hard"),
        ("Pragmatic", "præɡˈmætɪk", "Dealing with things sensibly and realistically in a way that is based on practical rather than theoretical considerations.", "She took a pragmatic approach to solving the administrative deadlock.", "practical, realistic", "idealistic, impractical", "medium"),
        ("Deduce", "dɪˈduːs", "Arrive at a fact or a conclusion by reasoning; draw as a logical conclusion.", "From the laboratory evidence, the investigators were able to deduce the cause of the reaction.", "infer, conclude", "", "medium"),
        ("Inductive", "ɪnˈdʌktɪv", "Characterized by the inference of general laws from particular instances.", "Inductive reasoning builds broad scientific generalizations from specific observations.", "empirical, generalized", "deductive", "hard"),
        ("Contradiction", "ˌkɑːntrəˈdɪkʃən", "A combination of statements, ideas, or features of a situation that are opposed to one another.", "The defendant's testimony contained a glaring contradiction.", "inconsistency, conflict", "agreement, consistency", "medium"),
        ("Cohesive", "koʊˈhiːsɪv", "Characterized by or causing cohesion; united.", "The chapter forms a cohesive narrative that links historical events smoothly.", "unified, connected", "fragmented, disjointed", "hard"),
        ("Scrutinize", "ˈskruːtənaɪz", "Examine or inspect closely and thoroughly.", "Peer reviewers carefully scrutinize every mathematical proof before approving publication.", "inspect, examine", "glance, overlook", "hard"),
        ("Substantiate", "səbˈstænʃieɪt", "Provide evidence to support or prove the truth of.", "The researcher was asked to substantiate her claims with experimental data.", "prove, verify", "disprove, refute", "hard"),
        ("Ambiguity", "ˌæmbɪˈɡjuːəti", "The quality of being open to more than one interpretation; inexactness.", "Technical writing must eliminate ambiguity to avoid operational errors.", "uncertainty, vagueness", "clarity, certainty", "medium"),
        ("Elucidate", "ɪˈluːsɪdeɪt", "Make something clear; explain.", "The keynote speaker used visual diagrams to elucidate complex astrophysical concepts.", "explain, clarify", "obscure, confuse", "hard")
    ],
    "Finance & Banking": [
        ("Dividend", "ˈdɪvɪdend", "A sum of money paid regularly by a company to its shareholders out of its profits.", "The corporation declared a quarterly dividend of fifty cents per share.", "shareholder payout, yield", "", "medium"),
        ("Inflation", "ɪnˈfleɪʃən", "A general increase in prices and fall in the purchasing value of money.", "Central banks raise interest rates to curb rising consumer inflation.", "price increase", "deflation", "medium"),
        ("Deflation", "diːˈfleɪʃən", "Reduction of the general level of prices in an economy.", "Prolonged deflation can discourage consumer spending and slow economic growth.", "price drop", "inflation", "medium"),
        ("Asset", "ˈæset", "A useful or valuable quality, person, or thing; property owned by a person or company.", "Real estate and stocks are key income-generating financial assets.", "property, holding", "liability, debt", "easy"),
        ("Liability", "ˌlaɪəˈbɪləti", "A thing for which someone is responsible, especially a debt or financial obligation.", "The company's balance sheet lists mortgage debts under long-term liabilities.", "debt, obligation", "asset", "medium"),
        ("Mortgage", "ˈmɔːrɡɪdʒ", "A legal agreement by which a bank lends money at interest in exchange for taking title of the debtor's property.", "They took out a thirty-year fixed-rate mortgage to purchase their family home.", "home loan", "", "medium"),
        ("Interest", "ˈɪntrəst", "Money paid regularly at a particular rate for the use of money lent, or for delaying the repayment of a debt.", "High-yield savings accounts offer four percent annual interest on cash deposits.", "finance charge, return", "", "easy"),
        ("Principal", "ˈprɪnsəpl", "A sum of money lent or invested on which interest is paid.", "Each monthly mortgage payment reduces both the principal and the accrued interest.", "capital, loan amount", "interest", "medium"),
        ("Portfolio", "pɔːrtˈfoʊlioʊ", "A range of investments held by a person or organization.", "A diversified investment portfolio helps mitigate market volatility risks.", "investment holdings", "", "medium"),
        ("Liquidity", "lɪˈkwɪdəti", "The availability of liquid assets to a market or company; the ease with which an asset can be converted into cash.", "Cash and government bonds provide high liquidity in times of financial emergency.", "cash flow, marketability", "illiquidity", "hard"),
        ("Recession", "rɪˈseʃən", "A period of temporary economic decline during which trade and industrial activity are reduced.", "During the economic recession, unemployment rose and retail spending decreased.", "economic downturn, slump", "boom, prosperity", "medium"),
        ("Bankruptcy", "ˈbæŋkrəptsi", "The state of being bankrupt; legal proceeding involving a person or business unable to repay debts.", "The retail chain filed for bankruptcy after accumulating unsustainable debts.", "insolvency, ruin", "solvency", "medium"),
        ("Collateral", "kəˈlætərəl", "Something pledged as security for repayment of a loan, to be forfeited in the event of a default.", "He offered his commercial building as collateral for the business expansion loan.", "security, guarantee", "", "hard"),
        ("Depreciation", "dɪˌpriːʃiˈeɪʃən", "A reduction in the value of an asset over time, due in particular to wear and tear.", "A new automobile suffers significant depreciation during its first two years on the road.", "devaluation, loss of value", "appreciation", "hard"),
        ("Appreciation", "əˌpriːʃiˈeɪʃən", "An increase in the value of an asset over time.", "Property appreciation in the metropolitan area averaged eight percent annually.", "value increase, gain", "depreciation", "medium"),
        ("Equity", "ˈekwəti", "The value of the shares issued by a company; the value of a property after subtracting mortgage debts.", "Homeowners build equity as they gradually pay down their home mortgage balance.", "ownership value, shares", "debt", "medium"),
        ("Fiscal", "ˈfɪskl", "Relating to government revenue, especially taxes, or financial matters in general.", "The government introduced a new fiscal policy to stimulate domestic manufacturing.", "financial, budgetary", "", "hard"),
        ("Hedge", "hedʒ", "Protect oneself against financial loss on other investments.", "Investors often purchase gold bullion as a hedge against currency inflation.", "protection, safeguard", "", "hard"),
        ("Venture Capital", "ˈventʃər ˈkæpɪtl", "Capital invested in a project in which there is a substantial element of risk, typically new businesses.", "The biotechnology startup raised ten million dollars in Series A venture capital.", "investment funding", "", "medium"),
        ("Yield", "jiːld", "The income return on an investment, such as the interest or dividends received from holding a particular security.", "Government treasury bonds offer a secure annual yield of four percent.", "return, profit", "", "medium"),
        ("Solvency", "ˈsɑːlvənsi", "The possession of assets in excess of liabilities; ability to pay one's debts.", "The bank audit confirmed the institution's robust financial solvency.", "financial health, stability", "insolvency, bankruptcy", "hard"),
        ("Arbitrage", "ˈɑːrbɪtrɑːʒ", "The simultaneous buying and selling of securities, currency, or commodities in different markets in order to take advantage of differing prices.", "Traders use automated algorithms to exploit currency arbitrage opportunities.", "price exploitation", "", "hard"),
        ("Audit", "ˈɔːdɪt", "An official inspection of an individual's or organization's accounts, typically by an independent body.", "The external accounting firm conducted a comprehensive annual financial audit.", "financial inspection, review", "", "medium"),
        ("Bull Market", "bʊl ˈmɑːrkɪt", "A market in which share prices are rising, encouraging buying.", "Optimistic investors celebrated as the technology sector entered a strong bull market.", "rising market", "bear market", "medium"),
        ("Bear Market", "ber ˈmɑːrkɪt", "A market in which prices are falling, encouraging selling.", "During a prolonged bear market, investors often rotate funds into defensive dividend stocks.", "falling market", "bull market", "medium"),
        ("Capital", "ˈkæpɪtl", "Wealth in the form of money or other assets owned by a person or organization.", "The founders invested fifty thousand dollars of seed capital into their bakery.", "funds, wealth", "", "easy"),
        ("Commodity", "kəˈmɑːdəti", "A raw material or primary agricultural product that can be bought and sold.", "Crude oil, wheat, and gold are actively traded on international commodity exchanges.", "raw material, trade good", "", "medium"),
        ("Default", "dɪˈfɔːlt", "Failure to fulfill an obligation, especially to repay a loan.", "Borrowers who default on their loans face severe damage to their credit scores.", "nonpayment, failure to pay", "repayment", "medium"),
        ("Diversification", "daɪˌvɜːrsɪfɪˈkeɪʃən", "The strategy of spreading investments across various financial instruments to reduce risk.", "Portfolio diversification protects investors against downturns in any single industry.", "spreading risk, variety", "concentration", "medium"),
        ("Gross Income", "ɡroʊs ˈɪnkʌm", "Total revenue or earnings before taxes, deductions, or operating expenses are subtracted.", "Her annual gross income before income tax deductions is eighty thousand dollars.", "total earnings, pre-tax", "net income", "easy"),
        ("Net Income", "net ˈɪnkʌm", "An individual's or business's total earnings after subtracting all deductions, taxes, and expenses.", "After deducting business expenses and corporate taxes, our net income grew by twelve percent.", "bottom line, profit", "gross income", "easy"),
        ("Overdraft", "ˈoʊvərdræft", "A deficit in a bank account caused by drawing more money than the account holds.", "The bank charged a small fee when his checking account went into overdraft.", "account deficit", "", "medium"),
        ("Underwrite", "ˈʌndərraɪt", "Sign and accept liability under an insurance policy, thus guaranteeing payment in case of loss or damage; undertake to finance.", "Investment banks agreed to underwrite the electric vehicle company's initial public offering.", "guarantee, finance", "", "hard"),
        ("Voucher", "ˈvaʊtʃər", "A document that serves as evidence of expenditure or that entitles the holder to a credit.", "The accounting department filed payment vouchers for every vendor check.", "receipt, coupon", "", "easy"),
        ("Withholding", "wɪðˈhoʊldɪŋ", "The deduction of an amount of money from an employee's paycheck for taxes.", "Employers calculate tax withholding based on the employee's tax allowance form.", "payroll tax deduction", "", "medium")
    ],
    "Programming & Software": [
        ("Refactoring", "riːˈfæktərɪŋ", "The process of restructuring existing computer code without changing its external behavior.", "Code refactoring improved application readability and reduced execution time.", "restructuring, code cleanup", "", "medium"),
        ("Asynchronous", "eɪˈsɪŋkrənəs", "Not occurring at the same time; denoting processes that operate independently of the main program flow.", "JavaScript uses asynchronous promises and async/await to handle API requests without freezing the UI.", "non-blocking, parallel", "synchronous, blocking", "hard"),
        ("Dependency", "dɪˈpendənsi", "A software library or module that another program relies upon to function.", "We run pip install to fetch all external dependencies listed in requirements.txt.", "library, package", "", "medium"),
        ("Polymorphism", "ˌpɑːliˈmɔːrfɪzəm", "The condition of occurring in several different forms; the ability of an object to take on many forms.", "Method overriding is a classic demonstration of runtime polymorphism in object-oriented programming.", "multiformity", "", "hard"),
        ("Encapsulation", "ɪnˌkæpsəˈleɪʃən", "The bundling of data with the methods that operate on that data, restricting direct access.", "Using private variables with public getters and setters provides strong data encapsulation.", "data hiding, bundling", "exposure", "hard"),
        ("Inheritance", "ɪnˈherɪtəns", "The mechanism of basing an object or class upon another object or class.", "The Dog subclass acquires shared animal properties through class inheritance.", "derivation, subclassing", "", "medium"),
        ("Middleware", "ˈmɪdlwer", "Software that acts as a bridge between an operating system or database and applications.", "Authentication middleware intercepts incoming HTTP requests to verify JWT tokens.", "bridge software", "", "medium"),
        ("Idempotent", "ˌaɪdɪmˈpoʊtənt", "Denoting an operation which can be applied multiple times without changing the result beyond the initial application.", "HTTP PUT and DELETE endpoints should always be designed to be idempotent.", "repeatable, consistent", "non-idempotent", "hard"),
        ("Endpoint", "ˈendpɔɪnt", "A specific URL where an API can access the resources it needs to carry out its function.", "The /api/dictionary/<word> endpoint returns standardized vocabulary information.", "API route, URL target", "", "easy"),
        ("Schema", "ˈskiːmə", "A representation of a plan or theory in the form of an outline or model; the structure of a database.", "The database schema defines table columns, foreign keys, and indexes.", "blueprint, data structure", "", "medium"),
        ("Serialization", "ˌsɪriələˈzeɪʃən", "The process of translating a data structure or object state into a format that can be stored or transmitted.", "JSON serialization converts Python dictionary objects into strings for API responses.", "encoding, marshaling", "deserialization, parsing", "hard"),
        ("Concurrency", "kənˈkɜːrənsi", "The ability of different parts or units of a program, algorithm, or problem to be executed out-of-order.", "Gunicorn workers provide concurrency by handling multiple web requests simultaneously.", "parallelism, multitasking", "sequential execution", "hard"),
        ("Decorator", "ˈdekəreɪtər", "A function that takes another function and extends the behavior of the latter function without modifying it.", "The @login_required decorator restricts access to authenticated users.", "function wrapper", "", "medium"),
        ("Singleton", "ˈsɪŋɡltən", "A software design pattern that restricts the instantiation of a class to one single instance.", "The database connection manager is implemented as a singleton.", "single instance", "", "hard"),
        ("Recursion", "rɪˈkɜːrʒən", "The process of defining a function in terms of itself.", "The algorithm traverses the binary search tree using recursive function calls.", "self-reference", "iteration", "medium"),
        ("Deprecated", "ˈdeprəkeɪtɪd", "Disapproved of; in software, software features that are superseded and should be avoided.", "The legacy database connection string is deprecated in SQLAlchemy 2.0.", "outdated, obsolete", "supported, recommended", "medium"),
        ("Immutable", "ɪˈmjuːtəbl", "Unchanging over time or unable to be changed.", "Python tuples and strings are immutable data structures.", "unalterable, constant", "mutable, changeable", "hard"),
        ("Mutable", "ˈmjuːtəbl", "Liable to change; capable of being mutated.", "Python lists and dictionaries are mutable objects that can be modified in place.", "changeable, alterable", "immutable, constant", "medium"),
        ("Repository", "rɪˈpɑːzətɔːri", "A central location in which data is stored and managed, especially source code in Git.", "Clone the GitHub repository to your local machine to begin development.", "repo, code store", "", "easy"),
        ("Commit", "kəˈmɪt", "Save changes to a repository in a version control system.", "Write descriptive commit messages to document code changes clearly.", "record, checkpoint", "", "easy"),
        ("Pull Request", "ˈpʊl rɪˌkwest", "A method of submitting contributions to an open-source project or shared repository.", "Teammates reviewed and approved the pull request before merging into main.", "PR, merge request", "", "easy"),
        ("Mock", "mɑːk", "An object that simulates the behavior of a real object in controlled ways for software testing.", "Unit tests use mock API responses to avoid calling live external services.", "stub, simulator", "real instance", "medium"),
        ("Deterministic", "dɪˌtɜːrmɪˈnɪstɪk", "Relating to the philosophical doctrine that all events are completely determined by previously existing causes; yielding the same output for a given input.", "Pure mathematical functions are deterministic and produce identical results every run.", "predictable, consistent", "stochastic, random", "hard"),
        ("Linting", "ˈlɪntɪŋ", "The automated checking of source code for programmatic and stylistic errors.", "Running a linter enforces consistent code styling and catches syntax bugs early.", "static analysis, code check", "", "medium"),
        ("Payload", "ˈpeɪloʊd", "The part of transmitted data that is the actual intended message.", "The HTTP POST request payload contains the user's login credentials in JSON format.", "body, data content", "metadata, headers", "medium"),
        ("Session", "ˈseʃən", "A temporary and interactive information interchange between two or more communicating devices or users.", "Flask stores encrypted user session cookies in the browser.", "connection, state", "", "easy"),
        ("Webhook", "ˈwebhʊk", "An HTTP-based callback function that allows lightweight, event-driven communication between APIs.", "GitHub sends a webhook notification whenever code is pushed to the repository.", "HTTP callback, event alert", "", "hard"),
        ("Microservice", "ˈmaɪkroʊsɜːrvɪs", "A software development technique that structures an application as a collection of loosely coupled services.", "The payment system was refactored into an independent microservice.", "modular service", "monolith", "hard"),
        ("Monolith", "ˈmɑːnəlɪθ", "A single-tiered software application in which different components combined into a single program.", "A monolithic web app is easier to develop and deploy in early startup stages.", "monolithic app", "microservices", "medium"),
        ("Cache", "kæʃ", "A hardware or software component that stores data so future requests for that data are served faster.", "Redis is widely used to cache frequent database queries in memory.", "buffer, temporary store", "", "medium"),
        ("Database Migration", "ˈdeɪtəbeɪs maɪˌɡreɪʃən", "The management of incremental, reversible changes and version control for relational database schemas.", "Flask-Migrate manages Alembic database migrations across staging and production.", "schema update", "", "medium"),
        ("Unit Test", "ˈjuːnɪt test", "A level of software testing where individual units or components of a software are tested in isolation.", "We wrote unit tests using Python's unittest module to verify dictionary lookup logic.", "component test", "integration test", "easy"),
        ("Integration Test", "ˌɪntɪˈɡreɪʃən test", "A level of software testing where individual units are combined and tested as a group.", "Integration tests ensure the database models and web routes cooperate smoothly.", "end-to-end test", "unit test", "medium"),
        ("Callback", "ˈkɔːlbæk", "A function passed as an argument to another function, to be invoked after an event.", "Pass a callback function to handle the asynchronous HTTP response when it arrives.", "hook, handler", "", "medium"),
        ("Exception", "ɪkˈsepʃən", "An event, which occurs during the execution of a program, that disrupts the normal flow of the program's instructions.", "The try-except block safely caught the database connection exception.", "error, runtime fault", "", "easy")
    ]
}


import time
import logging

logger = logging.getLogger(__name__)


def seed_database(app=None, verbose=True):
    """
    Seed database with 15 system vocabulary topics and 525 system vocabulary items.
    System topics and words are assigned user_id = None (public system data).

    Idempotent and safe to run multiple times without duplicating data or altering user data.
    Returns (topics_inserted, words_inserted).
    """
    if app is None:
        app = create_app()

    with app.app_context():
        # Fast-path check: if 15 system topics already exist with >= 525 words, skip
        total_topics_existing = Topic.query.filter(Topic.user_id.is_(None)).count()
        total_words_existing = Word.query.filter(Word.user_id.is_(None)).count()

        if total_topics_existing >= 15 and total_words_existing >= 525:
            all_present = all(
                Topic.query.filter(Topic.user_id.is_(None), func.lower(Topic.name) == func.lower(name)).first()
                for name in VOCAB_DATA.keys()
            )
            if all_present:
                msg = (f"[SEED] System vocabulary already present "
                       f"({total_topics_existing} system topics, "
                       f"{total_words_existing} system words). Skipping.")
                if verbose:
                    print(msg)
                else:
                    logger.info(msg)
                return 0, 0

        if verbose:
            print("[SEED] Seeding system vocabulary topics and words...")
        else:
            logger.info("[SEED] Seeding system vocabulary topics and words...")

        total_topics_seeded = 0
        total_words_seeded = 0

        for topic_name, words_list in VOCAB_DATA.items():
            # Check or create system topic (user_id = None)
            topic = Topic.query.filter(
                Topic.user_id.is_(None),
                func.lower(Topic.name) == func.lower(topic_name)
            ).first()
            if not topic:
                topic = Topic(name=topic_name, user_id=None)
                db.session.add(topic)
                db.session.flush()
                total_topics_seeded += 1
                if verbose:
                    print(f"[SEED] Created system topic: '{topic_name}'")
            elif verbose:
                print(f"[SEED] System topic already exists: '{topic_name}' (id={topic.id})")

            # Check or create system words in topic (user_id = None)
            for term, ipa, definition, example, synonyms, antonyms, difficulty in words_list:
                existing_word = Word.query.filter(
                    Word.topic_id == topic.id,
                    Word.user_id.is_(None),
                    func.lower(Word.term) == func.lower(term)
                ).first()

                if not existing_word:
                    new_word = Word(
                        term=term,
                        ipa=ipa,
                        definition=definition,
                        example_sentence=example,
                        synonyms=synonyms,
                        antonyms=antonyms,
                        difficulty=difficulty,
                        topic_id=topic.id,
                        user_id=None
                    )
                    db.session.add(new_word)
                    total_words_seeded += 1
                else:
                    # Backfill missing enrichment fields without overwriting existing data
                    if not existing_word.ipa and ipa:
                        existing_word.ipa = ipa
                    if not existing_word.synonyms and synonyms:
                        existing_word.synonyms = synonyms
                    if not existing_word.antonyms and antonyms:
                        existing_word.antonyms = antonyms


        db.session.commit()
        summary_msg = (f"[SEED] Seeding complete: inserted {total_topics_seeded} new topics, "
                       f"{total_words_seeded} new words.")
        if verbose:
            print(summary_msg)
        else:
            logger.info(summary_msg)

        return total_topics_seeded, total_words_seeded


def auto_init_and_seed(app, max_retries=3, retry_delay=2):
    """
    Production-safe database initialization and idempotent auto-seeding with retry.
    Called once during application startup.

    Flow:
        1. db.create_all() — ensures all tables exist
        2. seed_database() — inserts missing system topics/words, skips if already seeded
    """
    for attempt in range(1, max_retries + 1):
        try:
            with app.app_context():
                logger.info(f"[DB] Initializing database schema (attempt {attempt}/{max_retries})...")
                db.create_all()
                logger.info("[DB] Database schema ready.")

                logger.info("[SEED] Checking system vocabulary...")
                seed_database(app=app, verbose=False)
                logger.info("[APP] WebVocab startup auto-seed complete.")
                return True
        except Exception as exc:
            logger.warning(f"[DB] Initialization attempt {attempt} failed: {exc}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error("[DB] Database initialization failed after all retries.", exc_info=True)
                raise


if __name__ == '__main__':
    seed_database(verbose=True)