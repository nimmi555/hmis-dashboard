import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder

# --- PAGE CONFIGURATION & CSS HACKS ---
st.set_page_config(page_title="HMIS Anomalies", layout="wide", initial_sidebar_state="expanded")

# --- UNIFIED CUSTOM CSS: THE LOOKER STUDIO THEME & LAYOUT HACKS ---
st.markdown("""
    <style>
        /* =========================================
           1. THE "ZERO-HACK" LAYOUT
           ========================================= */
        /* We are NO LONGER touching the header, z-index, or toolbar. 
           This guarantees Streamlit will render the left arrow 100% natively. */
           
        .block-container {
            padding-top: 3rem !important; 
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-bottom: 1rem !important;
            max-width: 100% !important;
        }
        
        /* Gently hide the deploy button, leaving the rest of the header alone */
        .stAppDeployButton {
            display: none !important;
        }
        
        div.stMarkdown {
            margin-bottom: -15px !important;
        }
        
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.5rem !important;
        }

        /* =========================================
           2. COLORS & THEME (Looker Studio Style)
           ========================================= */
        .stApp {
            background-color: #fdfbed;
        }
        [data-testid="stSidebar"] {
            background-color: #f5f3e9;
        }
        [data-testid="stTabs"] {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
        }
        
        /* =========================================
           1. PROFESSIONAL LOOKER STUDIO TAB STYLING
           ========================================= */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background-color: #ffffff;
            padding: 10px 15px;
            border-radius: 12px;
            box-shadow: 0px 2px 8px rgba(0,0,0,0.06);
            border-bottom: 4px solid #4285F4;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #f1f3f4 !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            color: #3c4043 !important;
            font-size: 15px !important;
            font-weight: 800 !important;
            border: 1px solid #dadce0 !important;
            transition: all 0.2s ease-in-out;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #e8f0fe !important;
            color: #1a73e8 !important;
            border-color: #8ab4f8 !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1a73e8 !important; /* Professional Google Blue */
            color: white !important;
            border: 1px solid #1a73e8 !important;
            box-shadow: 0px 4px 10px rgba(26, 115, 232, 0.3);
        }
        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }

        /* =========================================
           2. EXECUTIVE SIDEBAR STYLING
           ========================================= */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
            border-right: 1px solid #e0e0e0;
            padding-top: 1rem;
        }
        
        /* Style the sidebar header titles */
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] label {
            color: #202124 !important;
            font-weight: 700 !important;
        }
        
        /* Custom styling for sidebar inputs and dropdowns */
        [data-testid="stSidebar"] div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] input {
            background-color: #ffffff !important;
            border-radius: 8px !important;
            border: 1px solid #ced4da !important;
        }
        
        /* Style the Search Action Button in Sidebar */
        [data-testid="stSidebar"] button[kind="secondary"] {
            background-color: #1a73e8 !important;
            color: white !important;
            border-radius: 8px !important;
            font-weight: bold !important;
            border: none !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background-color: #1557b0 !important;
        }
        
        /* --- CUSTOM HEADER & TILE STYLING --- */
        .ds-yellow-header {
            background-color: #e5ff4c;
            padding: 10px;
            border-radius: 20px;
            text-align: center;
            border: 1px solid #000;
            color: #0000bb;
            font-weight: bold;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .ds-orange-header {
            background-color: #ff5722;
            padding: 5px;
            border-radius: 10px;
            text-align: center;
            color: white;
            font-weight: bold;
            width: 400px;
            margin: 0 auto;
        }
        .kpi-tile {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
            border-top: 5px solid #4285F4;
        }
        .kpi-title {
            font-size: 20px;
            font-weight: 800;
            color: #333;
            margin-bottom: 10px;
        }
        .kpi-value {
            font-size: 38px;
            font-weight: bold;
            color: #000;
        }
        .chart-title {
            background-color: #cce5ff;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            font-size: 18px;
            font-weight: 800;
            color: #004085;
            margin-bottom: 15px;
            border: 1px solid #b8daff;
        }
        
        /* --- DOWNLOAD BUTTONS --- */
        div[data-testid="stDownloadButton"] > button {
            background-color: #198754 !important;
            color: white !important;
            border: none !important;
            font-weight: bold !important;
        }
        div[data-testid="stDownloadButton"] > button:hover {
            background-color: #146c43 !important;
        }
        [data-testid="stElementToolbarButton"] svg {
            width: 1.8rem !important;
            height: 1.8rem !important;
            color: #4285F4 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- LOAD ALL 525 METRICS ---
RAW_METRICS = """
1.1 :: Total number of NEW Pregnant Women registered for ANC
1.1.a :: Out of total number of NEW Pregnant Women registered with age less than <15 years
1.1.b :: Out of total number of NEW Pregnant Women registered with age 15-19 years
1.1.c :: Out of total number of NEW Pregnant Women registered with age more than >19 to 49 years
1.1.d :: Out of total number of NEW Pregnant Women registered with age more than >49 years
1.1.1 :: Out of the total NEW ANC registered, number registered within 1st trimester (within 12 weeks)
1.1.2 :: Total ANC footfall/cases (Old cases + New Registration) attended
1.2.1 :: Number of PW given Td1 (Tetanus Diptheria dose 1)
1.2.2 :: Number of PW given Td2 (Tetanus Diptheria dose 2)
1.2.3 :: Number of PW given Td Booster (Tetanus Diptheria dose booster)
1.2.4 :: Number of PW provided full course 180 Iron Folic Acid (IFA) tablets
1.2.5 :: Number of PW provided full course 360 Calcium tablets
1.2.6 :: Number of PW given one Albendazole tablet after 1st trimester
1.2.7 :: Number of PW received 4 or more ANC check ups
1.2.8 :: Number of PW given ANC Corticosteroids in Pre-Term Labour
1.3.1 :: New cases of PW with hypertension detected
1.3.2 :: Number of PW with hypertension managed at institution
1.3.3. :: Number of New Pre-Eclampsia/Eclampsia cases identified
1.3.4 :: Number of Pre-Eclampsia/Eclampsia cases managed during ANC
1.3.5 :: Number of Eclampsia cases managed during delivery
1.4.1. :: Number of PW tested for Haemoglobin (Hb) 4 or more than 4 times for respective ANCs
1.4.2. :: Number of PW tested for Haemoglobin (Hb)
1.4.3. :: Number of PW having Hb level<11(7.1 to 10.9 g/dl) (Out of total tested cases)
1.4.4. :: Number of PW having Hb level<=7 g/dl (Out of total tested cases)
1.4.5. :: Number of PW treated for severe anaemia (Hb<=7g/dl) (including referred-in cases)
1.5.1. :: Number of PW tested for Blood Sugar using OGTT(Oral Glucose Tolerance Test)
1.5.2. :: Number of PW tested positive for GDM out of total OGTT(Oral Glucose Tolerance Test) conducted
1.5.3. :: Number of GDM positive PW managed with Insulin/Metformin out of total tested positive for GDM
1.6.1.a :: Number of pregnant/Direct-In-Labor (DIL) women screened/tested (with VDRL/RPR/TPHA/RDT/PoC) for Syphilis
1.6.1.b :: Number of pregnant/DIL women found Seropositive for Syphilis by VDRL/RPR/TPHA/RDT/PoC test
1.6.1.c :: Number of pregnant/DIL women found Syphilis-Seropositive and given treatment with injection Benzathine Penicillin (IM)
1.6.1.d :: Number of live births among Syphilis Seropositive Pregnant Women
1.6.1.e :: Number of babies born to Syphilis-Seropositive Pregnant Women tested positive/ clinically diagnosed for congenital Syphilis
1.6.1.f :: Out of above, babies with congenital Syphilis received curative treatment
1.7.1. :: Number of Pregnant Women tested positive for Thyroid disorder
1.7.2. :: Number of Pregnant Women treated for thyroid disorder
1.8.1. :: Number of Pregnant Women screened for TB
1.8.2. :: Number of Pregnant Women identified with Presumptive TB symptoms
1.8.3. :: Number of Pregnant Women referred out of those identified with Presumptive TB symptoms
1.9.1. :: Total High Risk Pregnancy (HRP) Intrapartum including following:
1.9.1.a. :: Number of Pregnant Women only with Post-Partum Haemorrhage(Immediately after delivery) in the facility
1.9.1.b. :: Number of Pregnant Women only with Sepsis in the facility
1.9.1.c. :: Number of Pregnant Women identified only with Eclampsia in the facility
1.9.1.d. :: Number of Pregnant Women identified only with obstructed labour in the facility
1.9.1.e. :: Number of Pregnant Women identified with more than 1 complication listed above
1.9.2. :: Total High Risk Pregnancy (HRP) Antepartum (Only New Cases are to be reported)
1.9.3. :: Total no. of highrisk ANC cases referred to Higher/ any other facility (Referred out)
1.9.3.a. :: Total no. of Intrapartum/PNC High Risk Pregnancy cases referred to Higher/ any other facility (Referred out)
1.9.4. :: Total no. of highrisk ANC cases referred in to the facility (Referred in)
1.9.4.a. :: Total no. of Intrapartum/PNC High Risk Pregnancy cases attended or referred into the facility (Referred in)
2.1.1.a :: Number of Home Deliveries attended by Skill Birth Attendant(SBA) (Doctor/Nurse/ANM)
2.1.1.b :: Number of Home Deliveries attended by Non SBA
2.1.2. :: Number of PW given Tablet Misoprostol during home delivery
2.2. :: Number of Institutional Deliveries conducted (Including C-Sections)
2.2.1. :: Out of total institutional deliveries(excluding C-section), number of women stayed for 48 hours or more after delivery
2.2.2. :: Out of total Institutional deliveries, number of Institutional Deliveries (Excluding C-Sections) conducted at night (8 PM- 8 AM)
2.2.3. :: Out of total Institutional deliveries, number of institutional deliveries conducted at Midwifery Led Care Unit (MLCU)
2.3.1. :: Out of total number of delivery, PW with age less than <15 years
2.3.2. :: Out of total number of delivery, PW with age 15-19 years
2.3.3. :: Out of total number of delivery, PW with age more than >19-49 years
2.3.4. :: Out of total number of delivery, PW with age more than > 49 years
2.4. :: Number of newborns received 6/7 HBNC visits after Delivery (Home+ Institutional)
2.5. :: No. of identified Sick new-borns referred by ASHA to facility under HBNC Programme
2.6. :: Total number of Children received all scheduled 5 Home visits under HBYC
3.1. :: Total number of C -Section deliveries performed
3.1.1. :: Out of total C-sections, number performed at night (8 PM- 8 AM)
3.1.2. :: Out of total C-section, number of women stayed for 72 hours or more after delivery
4.1.1.a :: Live Birth - Male
4.1.1.b :: Live Birth - Female
4.1.2. :: Number of Pre-term newborns ( < 37 weeks of pregnancy)
4.1.3.a :: Fresh Stillbirth - Intrapartum Stillbirth (28 weeks & above)
4.1.3.b :: Mascerated Stillbirth – Antepartum Stillbirth (28 weeks &above)
4.1.3.c :: Foetal Death (24–27 completed weeks)
4.2. :: Abortion (spontaneous)
4.3.1.a :: Surgical MTPs upto 12 weeks of pregnancy
4.3.1.b :: MTP more than 12 weeks of pregnancy
4.3.1.c :: MTPs completed through Medical methods of abortion (MMA)
4.3.2.a :: Total Post-abortion/MTP Complications Identified
4.3.2.b. :: Post-abortion/MTP complications identified (where abortions were carried out in facilities other than public and accredited private health facilities)
4.3.2.c. :: Post-abortion/MTP Complications treated
4.3.3. :: Number of women provided with Post-abortion/ MTP contraception
4.4.1. :: Number of Newborns weighed at birth
4.4.2. :: Number of Newborns having weight less than 2500 gms
4.4.2.a :: Out of the above, number of Newborns having weight less than 1800 gms
4.4.3. :: Number of Newborns breast fed within 1 hour of birth
4.4.4. :: No. of Newborns discharged from the facility were exclusively breastfed till discharge
4.4.5 :: Number of Newborns received Donor Human Milk (DHM) in the facility
4.5.1. :: Number of Newborns screened for defects at birth (as per Comprehensive Newborn Screening, RBSK)
4.5.1.a :: Number of Newborns identified with visible birth defects (including Neural tube defect, Down’s Syndrome, Cleft Lip & Palate, Club foot and Developmental dysplasia of the hip)
4.5.3. :: Number of SNCU discharged babies screened in DEIC
4.5.5. :: Number of children till age 18 years (affected with selected health conditions) managed for 4 Ds (Disease, Deficiency, Developmental Delay & Defect)
4.5.6. :: Number of children till age 18 years (affected with selected health conditions) managed by Intervention - Surgical
4.5.7. :: Number of children till age 18 years managed at DEIC (District Early Intervention Centre)
5.1.1. :: Number of women of reproductive age (WRA) 20-49 years (non-pregnant, non-lactating), provided 4 Red Iron and folic acid (IFA) tablets in a month
5.1.2. :: Number of children (6-59 months old) provided 8-10 doses (1ml) of IFA syrup (Bi weekly)
5.1.3.a :: Number of out of school children (5 -9 years) given 4-5 IFA Pink tablets at Anganwadi Centres
5.2.1.c :: Number of out of school adolescent girls (10-19 years) having anaemia (Hb 8.1-11.9 g/dl)
5.2.1.e. :: Number of lactating mothers (of 0-6 months old child) having anaemia (Hb 8.1-11.9 g/dl)
5.2.1.f. :: Number of women of reproductive age (non-pregnant, non-lactating) (20-49 years) having anaemia (Hb 8.1-11.9 g/dl)
5.2.2.c :: Number of out of school adolescent girls (10-19 years) having severe anaemia (Hb <8 g/dl)
5.2.2.e :: Number of lactating mothers (of 0-6 months old child) having severe anaemia (Hb <8 g/dl)
5.2.2.f :: Number of women of reproductive age (non-pregnant, non-lactating) (20-49 years) having severe anaemia (Hb <8 g/dl)
5.2.3.a :: Number of anaemic in-school Children (5-9 years) put on treatment
5.2.3.b :: Number of anaemic in-school adolescent girls (10-19 years) put on treatment
5.2.3.c :: Number of anaemic out of school adolescent girls (10-19 years) put on treatment
5.2.3.d :: Number of anaemic in-school adolescent boys (10-19 years) put on treatment
5.2.3.e :: Number of anaemic lactating mothers (of 0-6 months old child) put on treatment
5.2.3.f :: Number of anaemic women of reproductive age (non-pregnant, non-lactating) (20-49 years) put on treatment
5.2.4.a :: Number of lactating mothers (of 0-6 months old child) diagnosed with severe anaemia and put on treatment
6.1. :: In case of home delivery, number of women receiving 1st Postpartum checkups within 48 hours
6.2. :: Number of women receiving Postpartum checkup between 48 hours and 14 days after Institutional delivery
6.3. :: Number of mothers provided full course of 180 IFA tablets after delivery
6.4. :: Number of mothers provided full course 360 Calcium tablets after delivery
6.5. :: Total No of High Risk Mothers identified during Post Natal Period
6.6. :: Out of above identified number of High Risk Mothers managed (including referred in cases)
7.1.1. :: Number of males assessed for STI/RTI
7.1.1.a :: Out of the above, number of males diagnosed with STI/RTI
7.1.1.b :: Out of the above, number of males treated for STI/RTI
7.1.2. :: Number of females (all females) assessed for STI/RTI
7.1.2.a :: Out of the above, number of females (all females) diagnosed with STI/RTI
7.1.2.b :: Out of the above, number of females (all females) treated for STI/RTI
7.1.3. :: Number of H/TG assessed for STI/RTI
7.1.3.a :: Out of the above, number of H/TG people diagnosed with STI/RTI
7.1.3.b :: Out of the above, number of H/TG people treated for STI/RTI
8.1.1. :: Number of Non Scalpel Vasectomy (NSV) / Conventional Vasectomy conducted
8.2.1. :: Number of Laparoscopic sterilizations (excluding post-abortion) conducted
8.2.2. :: Number of Interval sterilizations (Mini-lap/Conventional) (other than post-partum and post abortion) conducted
8.2.3. :: Number of Postpartum sterilizations (within 7 days of delivery by minilap or concurrent with caesarean section) conducted
8.2.4. :: Number of Post-abortion sterilizations (within 7 days of spontaneous or surgical abortion) conducted
8.3. :: Number of Interval IUCD Insertions (excluding PPIUCD and PAIUCD)
8.4. :: Number of Postpartum (within 48 hours of delivery) IUCD insertions
8.5. :: Number of Post-abortion (within 12 days of spontaneous or surgical abortion) IUCD insertions
8.6. :: Number of IUCD Removals
8.7. :: Number of complications following IUCD Insertion
8.8.1. :: Injectable Contraceptive MPA (Intra Muscular) - First Dose
8.8.2. :: Injectable Contraceptive MPA (Sub Cutaneous) - First Dose
8.9.1. :: Injectable Contraceptive MPA (Intra Muscular) - Second Dose
8.9.2. :: Injectable Contraceptive MPA (Sub Cutaneous)- Second Dose
8.10.1. :: Injectable Contraceptive MPA (Intra Muscular) - Third Dose
8.10.2. :: Injectable Contraceptive MPA (Sub Cutaneous)- Third Dose
8.11.1. :: Injectable Contraceptive MPA (Intra Muscular) - Fourth and above Dose
8.11.2. :: Injectable Contraceptive MPA (Sub Cutaneous)- Fourth and above Dose
8.12. :: Number of Combined Oral Pill cycles distributed to the beneficiary
8.13. :: Number of Condom pieces distributed to the beneficiary
8.14. :: Number of Centchroman (weekly) pill strips distributed to the beneficiary
8.15. :: Number of Emergency Contraceptive Pills (ECP) given to the beneficiary
8.16. :: Number of Pregnancy Test Kits (PTK) utilized
8.17.1 :: No. of Subdermal Contraceptive Implant inserted
8.17.2 :: No. of Subdermal Contraceptive Implant removed
8.18.1. :: Complications following male sterilization
8.18.2. :: Complications following female sterilization
8.18.3. :: Failures following male sterilization
8.18.4. :: Failures following female sterilization
8.18.5. :: Deaths following male sterilization
8.18.6. :: Deaths following female sterilization
8.19.1. :: Number of cases of Female Sterilization followed up (after 1 month or on the resumption of her menstrual cycle whichever is earlier)
8.19.2. :: Number of cases of Male Sterilization followed up (after 3 months)
9.1.1. :: Child immunisation - Vitamin K (Birth Dose)
9.1.2. :: Child immunisation - BCG
9.1.3. :: Child immunisation - Pentavalent 1
9.1.4. :: Child immunisation - Pentavalent 2
9.1.5. :: Child immunisation - Pentavalent 3
9.1.6. :: Child immunisation - OPV 0 (Birth Dose)
9.1.7. :: Child immunisation - OPV1
9.1.8. :: Child immunisation - OPV2
9.1.9. :: Child immunisation - OPV3
9.1.10. :: Child immunisation - Hepatitis-B0 (Birth Dose)
9.1.11. :: Child immunisation - Inactivated Injectable Polio Vaccine 1 (IPV 1)
9.1.12. :: Child immunisation - Inactivated Injectable Polio Vaccine 2 (IPV 2)
9.1.13. :: Child immunisation - Rotavirus 1
9.1.14. :: Child immunisation - Rotavirus 2
9.1.15. :: Child immunisation - Rotavirus 3
9.1.16. :: Child immunisation - PCV1
9.1.17. :: Child immunisation - PCV2
9.2.1. :: Child immunisation(9 - 11 months) - Inactivated Injectable Polio Vaccine 3 (IPV 3)
9.2.2. :: Child immunisation (9-11months) - Measles & Rubella (MR)/Measles containing vaccine(MCV) - 1st Dose
9.2.3. :: Child immunisation (9-11months) - JE 1st dose
9.2.4. :: Child immunisation - PCV Booster
9.2.5.a :: FULLY IMMUNIZED children aged between 9 and <12 months- Male
9.2.5.b :: FULLY IMMUNIZED children aged between 9 and <12 months- Female
9.3.1. :: Child immunisation(after 12 months-delayed vaccination) - Measles & Rubella (MR)/Measles containing vaccine(MCV)- 1st Dose
9.3.2. :: Child immunisation (after 12 months-delayed vaccination) - JE 1st dose
9.3.3. :: Child immunisation - DPT 1 after 12 months of age (delayed vaccination)
9.3.4. :: Child immunisation - DPT 2 after 12 months of age (delayed vaccination)
9.3.5. :: Child immunisation - DPT 3 after 12 months of age (delayed vaccination)
9.3.6. :: Child immunisation - DPT Booster after 24 months of age (delayed vaccination)
9.3.7. :: Child immunisation - OPV Booster after 24 months of age (delayed vaccination)
9.3.8. :: Child immunisation - JE Booster after 24 months of age (delayed vaccination)
9.4.1. :: Child immunisation - Measles & Rubella (MR)/ Measles containing vaccine(MCV)- 2nd Dose (16-24 months)
9.4.2. :: Child immunisation - DPT 1st Booster
9.4.3. :: Child immunisation - OPV Booster
9.4.4. :: Number of children more than 16 months of age who received Japanese Encephalitis (JE) vaccine- 2nd dose (16-24 months)
9.5.1. :: Child Immunization- Typhoid
9.5.2. :: Children more than 5 years received DPT5 (2nd Booster)
9.5.3. :: Children more than 10 years received Td10 (Tetanus Diptheria10)
9.5.4. :: Children more than 16 years received Td16 (Tetanus Diptheria16)
9.6.1. :: Number of cases of AEFI -Minor (eg.- fever, rash, pain etc)
9.6.2. :: Number of cases of AEFI - Severe (eg.- anaphylaxis, fever>102 degrees, not requiring hospitalization etc.)
9.6.3. :: Number of cases of AEFI - Serious (eg.- hospitalization, death, disability , cluster etc.)
9.6.3.a :: Out of Number of cases of AEFI - Serious , total number of AEFI deaths
9.7.1. :: Immunisation sessions planned
9.7.2. :: Immunisation sessions held
9.8.1. :: Child immunisation - Vitamin A Dose - 1
9.8.2. :: Child immunisation - Vitamin A Dose - 5
9.8.3. :: Child immunisation - Vitamin A Dose - 9
10.1.1. :: Childhood Diseases - Pneumonia
10.1.2. :: Childhood Diseases - Asthma
10.1.3. :: Childhood Diseases - Sepsis
10.1.4. :: Childhood Diseases - Diphtheria
10.1.5. :: Childhood Diseases - Pertussis
10.1.6. :: Childhood Diseases - Tetanus Neonatorum
10.1.7. :: Childhood Diseases - Tuberculosis (TB)
10.1.8. :: Childhood Diseases - Acute Flaccid Paralysis(AFP)
10.1.9. :: Childhood Diseases - Measles
10.1.10. :: Childhood Diseases - Malaria
10.1.11. :: Childhood Diseases - Diarrhoea
10.1.12. :: Childhood Diseases - Diarrhoea treated with ORS
10.1.13. :: Childhood Diseases - Diarrhoea treated with Zinc for 14 days
10.1.14. :: Childhood Diseases -Leprosy Cases
10.1.15. :: Childhood Diseases- Leprosy with Grade II disability
10.2.1. :: Children admitted with Respiratory Infections
10.2.2. :: Children admitted with Pneumonia
10.2.3. :: Children admitted with Diarrhoea
11.1.1.a :: Total Blood Smears Examined for Malaria
11.1.1.b :: Malaria (Microscopy Tests ) - Plasmodium Vivax test positive
11.1.1.c :: Malaria (Microscopy Tests ) - Plasmodium Falciparum test positive
11.1.1.d :: Malaria (Microscopy Tests ) - Mixed test positive
11.1.2.a :: RDT conducted for Malaria
11.1.2.b :: Malaria (RDT) - Plasmodium Vivax test positive
11.1.2.c :: Malaria (RDT) - Plasmodium Falciparum test positive
11.1.2.d :: Malaria (RDT) - Mixed test positive
11.2.1. :: Kala Azar (RDT) - Tests Conducted
11.2.2. :: Kala Azar Positive Cases
11.3.1. :: Dengue - Enzyme- Linked Immuno Sorbent Assay (ELISA) test conducted
11.3.2. :: Dengue - Enzyme- Linked Immuno Sorbent Assay (ELISA) test found positive
11.3.3. :: Chikungunya Enzyme- Linked Immuno Sorbent Assay (ELISA) test conducted
11.3.4. :: Chikungunya Enzyme- Linked Immuno Sorbent Assay (ELISA) test found positive
11.4.1. :: No. of AES cases tested for JE(IgM ELISA)
11.4.2. :: No. of JE positive cases
11.5.1. :: Number of persons that consumed MDA(Mass Drug Administration) drugs during the MDA round
11.5.2. :: Number of Lymphatic Filarisis lymphoedema patients received MMDP (Morbidity Management And Disability Prevention) kits
11.5.3. :: Number of Hydrocele surgeries conducted in Lymphatic Filariasis (MMDP)
12.1.1.a :: Girls registered in AFHC
12.1.1.b :: Boys registered in AFHC
12.1.2.a :: Out of Girls registered, Girls received clinical services
12.1.2.b :: Out of Boys registered, Boys received clinical services
12.1.3.a :: Out of Girls registered, Girls received counselling
12.1.3.b :: Out of Boys registered, Boys received counselling
12.3.1. :: Number of adolescent girls provided sanitary napkin packs by ASHA
12.3.2. :: Number of sanitary napkin packs distributed free to ASHA (for her personal use)
12.3.3. :: Number of adolescent girls attended monthly meeting
12.3.4. :: Number of adolescent girls provided sanitary napkin packs by State/UT supported Menstrual Hygiene Scheme (MHS)
12.4.1. :: Number of Peer Educators selected
12.4.2. :: Out of the selected Peer Educators, numbers trained
12.4.3. :: Number of Adolescent Health & Wellness Days organized
12.4.4. :: Number of Adolescent Friendly Club Meetings organized
13.1. :: Number of beneficiaries who are registered at the ICTC centre.
13.2. :: Of the number registered at ICTC centre, the number presumptive TB cases identified and referred for TB testing and diagnosis
13.3. :: Number of beneficiaries who are registered at the NCD clinic.
13.4. :: The number registered at the NCD clinic includes the number of presumptive TB cases identified and referred for TB testing and diagnosis
14.1.1.a :: Total number of geriatric/elderly patients (age>=60 yrs) Registered
14.1.1.b :: Geriatric (age>=60 yrs) patients footfall
14.1.1.c :: Number of geriatric/elderly persons who underwent Comprehensive Geriatric Assessment by CHO
14.1.1.d :: Number of geriatric/elderly persons managed for any elderly conditions
14.1.1.e :: Number of geriatric/elderly persons followed-up for any elderly conditions
14.1.1.f :: Number of geriatric/elderly patients (age>=60 yrs) provided physiotherapy services
14.1.1.g :: Number of home bound (bed bound & restricted mobility) elderly and single elderly visited by ASHA & ANM/MPW-M during the month
14.1.1.h :: Number of elderly support groups-‘Sanjeevini’ created during the month
14.1.1.i :: Number of weekly geriatric clinics organized during the month
14.1.1.j :: Number of fixed day rehabilitation services provided during the month
14.1.2.a. :: Number of patients provided physiotherapy services
14.1.2.b. :: Number of Palliative Patients visited at home
14.1.2.c. :: Number of visits for home care/ end of life care provided by AAM-PHC team
14.1.2.d. :: Number of weekly palliative care OPD conducted at AAM-PHC
14.1.2.e. :: Number of cases reported for Self Harm
14.1.3.a :: Total number of footfall in outreach camps/sessions
14.1.3.b :: Total number cases examined in outreach camps for Mental illness
14.1.4. :: Number of psychoeducation sessions conducted at the Ayushman Arogya Mandir during the month
14.2.1. :: Allopathic- Outpatient attendance
14.2.1.a :: Out of above, number of specialist Allopathic OPD services provided
14.2.2. :: Ayush - Outpatient attendance
14.2.2.b :: Out of above, number of specialist AYUSH OPD services provided
14.3.1.a :: IPD Admission Male- Children<18yrs
14.3.1.b :: IPD Admission Male- Adults <60yrs
14.3.1.c :: IPD Admission Female- Children<18yrs
14.3.1.d :: IPD Admission Female- Adults<60yrs
14.3.1.e :: IPD Admission Geriatric->=60yrs
14.3.2.a :: IPD Discharge Male- Children<18yrs
14.3.2.b :: IPD Discharge Male- Adults<60yrs
14.3.2.c :: IPD Discharge Female- Children<18yrs
14.3.2.d :: IPD Discharge Female- Adults<60yrs
14.3.2.e :: IPD Discharge Geriatric->=60yrs
14.3.3.a :: IPD Referred Male- Children<18yrs
14.3.3.b :: IPD Referred Male- Adults<60yrs
14.3.3.c :: IPD Referred Female- Children<18yrs
14.3.3.d :: IPD Referred Female- Adults<60yrs
14.3.3.e :: IPD Referred Geriatric->=60yrs
14.3.4.a :: IPD Deaths Male- Children<18yrs
14.3.4.b :: IPD Deaths Male- Adults<60yrs
14.3.4.c :: IPD Deaths Female- Children<18yrs
14.3.4.d :: IPD Deaths Female- Adults<60yrs
14.3.4.e :: IPD Deaths Geriatric->=60yrs
14.3.5.a :: Total cases Referred out (OPD+IPD+Emergency)-During Day
14.3.5.b :: Total cases Referred out (OPD+IPD+Emergency)-At Night (8 PM- 8 AM)
14.3.6. :: Day Care Admissions
14.3.7.a :: Number of Total Left Against Medical Advice (LAMA) cases reported at the facility
14.3.7.b :: Number of delivery LAMA cases reported at the facility
14.3.8 :: Total number of Medico Legal Cases reported at the facility
14.3.9 :: Total number of postmortem conducted at the facility
14.3.10. :: Total number of telemedicine consultation provided
14.4.1. :: Inpatient - Malaria
14.4.2. :: Inpatient - Dengue
14.4.3. :: Inpatient - Typhoid
14.4.4. :: Inpatient - Asthma, Chronic Obstructive Pulmonary Disease (COPD), Respiratory infections
14.4.5. :: Inpatient - Tuberculosis
14.4.6. :: Inpatient - Pyrexia of unknown origin (PUO)
14.4.7. :: Inpatient - Diarrhoea with dehydration
14.4.8. :: Inpatient – Leprosy (Reconstructive Surgery)
14.4.9. :: Inpatient – Operated for Cataract
14.4.10. :: Inpatient – Palliative Care
14.4.11. :: Inpatient – Mental illness
14.5.1. :: Patients registered at Emergency Department
14.5.2. :: No. of Emergencies managed at night (8 PM- 8 AM)
14.5.3. :: Total Number of Emergency cases managed
14.5.4. :: Total Number of Emergency cases referred out
14.5.5. :: Total Number of CPR performed in the emergency
14.6.1.a :: Emergency - Trauma ( accident, injury, poisoning etc) -Admission
14.6.1.b :: Emergency - Trauma ( accident, injury, poisoning etc) -Deaths
14.6.2.a :: Emergency - Burn -Admission
14.6.2.b :: Emergency - Burn -Deaths
14.6.3.a :: Emergency - Obstetrics complications -Admission
14.6.3.b :: Emergency - Obstetrics complications -Deaths
14.6.4.a :: Emergency - Snake Bite -Admission
14.6.4.b :: Emergency - Snake Bite -Deaths
14.6.5.a :: Emergency - Acute Cardiac Emergencies -Admission
14.6.5.b :: Emergency - Acute Cardiac Emergencies -Deaths
14.6.6.a :: Emergency - CVA (Cerebrovascular Disease)/Stroke -Admission
14.6.6.b :: Emergency - CVA (Cerebrovascular Disease)/Stroke -Deaths
14.6.7.a :: Emergency - Dog Bite -Admission
14.6.7.b :: Emergency - Dog Bite -Deaths
14.7. :: Total number of deaths occurring at Emergency Department
14.8.1.a :: Total number of Major Operations conducted excluding C-Section (General and spinal anaesthesia)
14.8.1.b :: Out of Major Operation, Gynecology- Hysterectomy surgeries
14.8.1.c :: Major Surgeries excluding Obstetrics, Gynaecology and Opthalmology.
14.8.1.d :: No. of Major Surgeries done at night (8PM to 8 AM) (Excluding C section)
14.8.2. :: Minor Operations (No or local anaesthesia)
14.9. :: Number of post operative Surgical Site infection
14.10. :: In-Patient Head Count at midnight
14.11.1 :: Number of Admission in NBSU ( New Born Stabilisation Unit)
14.11.2. :: Number of total admissions in Special Newborn Care Unit (SNCU Admissions)
14.12.1 :: Number of deaths occurred at SNCU
14.12.2 :: Number of Newborns successfully discharged from SNCU
14.13.1.a.i :: Number of pregnant women provided free medicines during ANC period under JSSK
14.13.1.a.ii :: Number of Pregnant women provided free medicines during delivery under JSSK
14.13.1.a.iii :: Number of PNC mothers provided free medicines under JSSK
14.13.1.b :: Number of women provided - Free Diet under JSSK
14.13.1.c.i :: Number of pregnant women provided free diagnostics during ANC period under JSSK
14.13.1.c.ii :: Number of Pregnant women provided free diagnostics during delivery under JSSK
14.13.1.c.iii :: Number of PNC mothers provided free diagnostics under JSSK
14.13.1.d :: Number ofpregnant women provided - Free Home to facility transport for conducting delivery under JSSK
14.13.1.e :: Number of pregnant women provided - Interfacility transfers when needed during delivery under JSSK(in case of referral)
14.13.1.f :: Number of PNC mothers provided - Free Drop Back home after delivery under JSSK
14.13.2.a :: Number of infants admitted at facility due to any sickness- JSSK Beneficiaries
14.13.2.b :: Number of sick infants provided - Free Medicines under JSSK
14.13.2.c :: Number of sick infants provided - Free Diagnostics under JSSK
14.13.2.d :: Number of sick infants provided - Free Home to facility transport under JSSK
14.13.2.e :: Number of infants received free referral transport under JSSK
14.14.1. :: Number of sick SAM children admitted in standalone/ integrated NRC
14.14.2. :: Number of sick SAM children referred to standalone/ integrated NRC by Frontline Workers (AWW/ ASHA/ ANM)
14.14.3. :: Number of sick SAM children referred to standalone/ integrated NRC from IPD/OPD of other Health Facility (PHC/CHC/SDH/DH/other NRC)
14.14.4. :: Number of children Referred to standalone/ integrated NRC by RBSK Team
14.14.5. :: Number of SAM children discharged from standalone/ integrated NRC who met the discharge criteria
14.14.6. :: Number of admitted children left against medical advice (LAMA) / defaulter
14.14.7. :: Number of children died while admitted in standalone/ intergrated NRC
14.14.8. :: Number of children who completed all four post discharge follow-ups
14.14.9. :: Number of sick SAM children treated and admitted in the pediatric facility (other than standalone/ integrated NRC)
14.14.10. :: In-Patient Head Count at midnight for standalone/ integrated NRC
14.15.1. :: Number of Rogi Kalyan Samiti (RKS) meetings held
14.15.2. :: Number of Jan Arogya Samiti (JAS) meetings held
14.16. :: Number of Anganwadi centres reported to have conducted atleast one Village Health & Nutrition Day (VHNDs)/UHND/ Outreach / Special Outreach sessions
14.17. :: Total number of UHND/VHND sessions conducted in the reporting month
14.18. :: Total number of Outreach/Special Outreach camps conducted in the reporting month
14.18.1. :: Total number of outreach visits conducted by staff
14.18.2. :: Total number of outreach visits made by DMHP team
14.18.3 :: Total number of awareness campaigns/camps conducted for Mental Health
14.19. :: Patient Satisfaction Score of the facility in percentage (from Mera Aspatal)
14.20.1.a :: Total number of blood samples screened by ELISA/Rapid tests for viral hepatitis A (IgM Anti- HAV)
14.20.1.b :: Total number of blood samples screened by ELISA/Rapid tests for viral hepatitis B i.e. HBsAg (excluding pregnant women)
14.20.1.c :: Total number of blood samples screened by ELISA/Rapid tests for viral hepatitis C(Anti- HCV)
14.20.1.d :: Total number of blood samples screened by ELISA/Rapid tests for viral hepatitis E(i.e. IgM Anti-HEV)
14.20.2.a :: Total number of blood samples tested positive by ELISA/ Rapid tests for Hepatitis A (out of those tested for IgM Anti- HAV)
14.20.2.b :: Total number of blood samples tested positive by ELISA/ Rapid tests for Hepatitis B (out of those tested for HBsAg excluding pregnant women)
14.20.2.b.i :: Total number of positive blood samples for hepatitis B by ELISA/ Rapid tests tested for HBV DNA(out of those tested positive for HBsAg excluding pregnant women)
14.20.2.b.ii :: Total number of patients found positive for HBsAg eligible for treatment for hepatitis B (excluding pregnant women)
14.20.2.b.iii :: Total number of patients eligible for treatment for Hepatitis B put on treatment(out of those eligible for treatment excluding pregnant women)
14.20.2.c :: Total number of blood samples tested positive by ELISA/ Rapid tests for Hepatitis C (out of those tested for Anti-HCV)
14.20.2.c.i :: Total number of positive blood samples for Hepatitis C screened by test (ELISA/ Rapid tests) confirmed by HCV RNA testing (out of those positive for anti-HCV)
14.20.2.c.ii :: Total number of patients put on treatment for Hepatitis C (out of those confirmed by HCV RNA i.e. HCV RNA detected)
14.20.2.c.iii :: Total number of positive Hepatitis C patients who have completed treatment
14.20.2.c.iv :: Total number of patients cleared for HCV RNA on sustained virological response at 12 weeks (SVR12)
14.20.2.d :: Total number of blood samples tested positive by ELISA/ Rapid tests for Hepatitis E(out of those tested for IgM Anti-HEV)
14.20.3.a :: Number of Pregnant Women tested for HBsAg
14.20.3.b :: Number of Pregnant Women who are HBsAg positive(out of those tested for Hepatitis B i.e. HBsAg)
14.20.3.c :: Number of Pregnant Women found positive for HBsAg referred out to higher centre for institutional delivery
14.20.3.d :: Number of Pregnant Women found positive for HBsAg delivered in an institution
14.20.3.e :: Number of newborn who received birth dose of Hepatitis B vaccine born to HBsAg positive pregnant women
14.20.3.f :: Number of New Borns to Pregnant Women (found positive for HBsAg) received Hepatitis B Immunoglobulin (HBIG) (within 24 hours of birth)
15.1.1. :: Total Number of Lab Tests done- Inhouse (including kits tests conducted in Laboratory)
15.1.2. :: Total Number of Lab Tests done- Outsourced (including kits tests conducted in Laboratory)
15.1.3. :: Total Number of Kit Tests conducted in Outreach areas/Camps/in-facility(outside lab)
15.2.1. :: Number of Hb tests conducted including kit tests
15.2.2. :: Out of the total number of Hb tests done, Number having Hb < 7 mg
15.3.1.a :: Number of males screened for HIV by Whole Blood Finger Prick/RDT test/POC test
15.3.1.b :: Out of the above, No. of males found reactive for HIV
15.3.1.c :: No. of males subjected to HIV test at Confirmatory Centre/Stand Alone-ICTC
15.3.1.d :: Out of the above, No. of males confirmed as HIV Positive
15.3.2.a :: Number of females (non-ANC) screened for HIV by Whole Blood Finger Prick/RDT test/POC test
15.3.2.b :: Out of the above, No. of females (non-ANC) found reactive for HIV
15.3.2.c :: No. of females (non-ANC) subjected to HIV test at Confirmatory Centre/Stand Alone-ICTC
15.3.2.d :: Out of the above, No. of females (non-ANC) confirmed as HIV Positive
15.3.3.a :: Number of Pregnant Women (PW-ANC) screened for HIV by Whole Blood Finger Prick/RDT test/POC test
15.3.3.b :: Out of the above, No. of PW(ANC) found reactive for HIV
15.3.3.c :: No. of PW(ANC) subjected to HIV test at Confirmatory Centre/Stand Alone-ICTC
15.3.3.d :: Out of the above, No. of PW(ANC) confirmed as HIV Positive
15.3.3.e :: Number of DIL women screened for HIV by Whole Blood Finger Prick/RDT test/POC test
15.3.3.f :: Out of the above, No. of DIL women found reactive for HIV
15.3.3.g :: No. of DIL women subjected to HIV test at Confirmatory Centre/Stand Alone-ICTC
15.3.3.h :: Out of the above, No. of DIL women confirmed as HIV Positive
15.3.3.i :: Number of Pregnant Women (ANC&DIL) screened for HIV more than once(Repeated testing)
15.3.4.a :: Number of H/TG people screened for HIV by Whole Blood Finger Prick/RDT test/POC test
15.3.4.b :: Out of the above, No. of H/TG people found reactive for HIV
15.3.4.c :: No. of H/TG people subjected to HIV test at Confirmatory Centre/Stand Alone-ICTC
15.3.4.d :: Out of the above, No. of H/TG people confirmed as HIV Positive
15.4.1.a :: Total number of males tested for Syphilis (RPR/VDRL/PoC/ RDT/TPHA)
15.4.1.b :: Out of the above, number of males tested reactive for Syphilis (RPR/VDRL/PoC/ RDT/TPHA)
15.4.1.c :: Out of the above, number of males treated for Syphilis
15.4.2.a :: Total number of female (non-ANC) tested for Syphilis (RPR/VDRL/PoC/ RDT/TPHA)
15.4.2.b :: Out of the above, number of females (non-ANC) tested reactive for Syphilis (RPR/VDRL/PoC/ RDT/TPHA)
15.4.2.c :: Out of the above, number of females (non-ANC) treated for Syphilis
15.4.3.a :: Total number of H/TG people tested for Syphilis (RPR/VDRL/PoC/ RDT/TPHA)
15.4.3.b :: Out of the above, number of H/TG people tested reactive for Syphilis (RPR/VDRL/PoC/ RDT/TPHA)
15.4.3.c :: Out of the above, number of H/TG people treated for Syphilis
15.5.1 :: Widal tests- Number Tested
15.5.2 :: Widal tests- Number Positive
15.6.1.a.i :: X-ray(Inhouse)
15.6.1.a.i.1 :: X-ray(Inhouse)-No. of chest X-rays done on patients with health risks- Diabetes, HIV, Smoking, Alcoholism, low BMI, geriatric population (>60),history of TB, contacts of TB
15.6.1.a.ii :: X-ray(Outsource)
15.6.1.b.i :: Ultrasonography (USG) (Inhouse)
15.6.1.b.ii :: Ultrasonography (USG)(Outsource)
15.6.1.c.i :: CT scan (Inhouse)
15.6.1.c.ii :: CT scan (Outsource)
15.6.1.d.i :: MRI (Inhouse)
15.6.1.d.ii :: MRI (Outsource)
15.6.1.e.i :: ECG (Inhouse)
15.6.1.e.ii :: ECG (Outsource)
16.1.1a :: New born deaths within 24 hrs(1 to 23 Hrs 59 minutes) of birth at Facility/Facility to facility in transit
16.1.1.b :: New born deaths within 24 hrs(1 to 23 Hrs 59 minutes) of birth in Community (at home or home to facility transit)
16.1.2.a :: New born deaths within 1 week (1 to 7 days) at Facility/Facility to facility in transit
16.1.2.b :: New born deaths within 1 week (1 to 7 days) At Community (at home or home to facility transit)
16.1.3.a :: New born deaths within 8 to 28 days at Facility/Facility to facility in transit
16.1.3.b :: New born deaths within 8 to 28 days At Community (at home or home to facility transit)
16.1.4.a :: Infant Deaths (>28 days to below 12 months) at Facility/Facility to facility in transit
16.1.4.b :: Infant Deaths (>28 days to below 12 months) At Community (at home or home to facility transit)
16.2.1. :: Neonatal Deaths up to 4 weeks (0 to 28 days) due to Sepsis
16.2.2. :: Neonatal Deaths up to 4 weeks (0 to 28 days) due to Asphyxia
16.2.3. :: Neonatal Deaths up to 4 weeks (0 to 28 days) due to complications of Prematurity
16.2.4. :: Neonatal Deaths up to 4 weeks (0 to 28 days) due to Other causes
16.3.1. :: Number of Infant Deaths (>28 days - below 12 months) due to Pneumonia
16.3.2. :: Number of Infant Deaths (>28 days - below 12 months) due to Diarrhoea
16.3.3. :: Number of Infant Deaths (>28 days - below 12 months) due to Fever related
16.3.4. :: Number of Infant Deaths (>28 days - below 12 months) due to Measles
16.3.5. :: Number of Infant Deaths (>28 days - below 12 months) due to Others
16.4.1. :: Number of Child Deaths (1 - below 5 years) due to Pneumonia
16.4.2. :: Number of Child Deaths (1 - below 5 years) due to Diarrhoea
16.4.3. :: Number of Child Deaths (1 - below 5 years) due to Fever related
16.4.4. :: Number of Child Deaths (1 - below 5 years) due to Measles
16.4.5. :: Number of Child Deaths (1 - below 5 years) due to Others
16.5.1. :: Number of Maternal Deaths at facility due to APH (Antepartum Haemmorhage)
16.5.2. :: Number of Maternal Deaths at facility due to PPH (Post-Partum Haemmorhage)
16.5.3. :: Number of Maternal Deaths at facility due to Pregnancy related infection and sepsis, Fever
16.5.4. :: Number of Maternal Deaths at facility due to Abortion and/ or its complication
16.5.5. :: Number of Maternal Deaths at facility due to Obstructed/prolonged labour
16.5.6. :: Number of Maternal Deaths at facility due to Severe hypertension/fits/Pre Eclampsia/Eclampsia in pregnancy, during delivery and puerperium
16.5.7. :: Number of Maternal Deaths at facility due to Other/Unknown Causes
16.5.8. :: Age wise total Maternal Deaths, occurred at Facility
16.5.8.a :: Out of total number of maternal deaths at facility, deaths with age less than <15 years
16.5.8.b :: Out of total number of maternal deaths at facility, deaths with age 15-19 years
16.5.8.c :: Out of total number maternal deaths at facility, deaths with age more than >19-49 years
16.5.8.d :: Out of total number maternal deaths at facility, deaths with age more than >49 years
16.6. :: Total Facility Based Maternal Death Reviews (FBMDR) done
16.7.1. :: Number of deaths due to Diarrhoeal diseases
16.7.2. :: Number of deaths due to Tuberculosis
16.7.3. :: Number of deaths due to Respiratory diseases including infections (other than TB)
16.7.4. :: Number of deaths due to Other Fever Related
16.7.5. :: Number of deaths due to Heart disease/Hypertension related
16.7.6. :: Number of deaths due to Cancer
16.7.7. :: Number of deaths due to Neurological disease including strokes
16.7.8. :: Number of deaths due to Accidents/Burn cases
16.7.9. :: Number of deaths due to Animal bites and stings
16.7.10. :: Number of deaths due to Known Acute Disease
16.7.11. :: Number of deaths due to Known Chronic Disease
16.7.12. :: Number of deaths due to Other Causes
16.8.1. :: Number of Deaths due to Malaria- Plasmodium Vivax
16.8.2. :: Number of Deaths due to Malaria- Plasmodium Falciparum
16.8.3. :: Number of Deaths due to Kala Azar
16.8.4. :: Number of Deaths due to Dengue
16.8.5. :: Number of Deaths due to Acute Encephelitis Syndrome (AES)
16.8.6. :: Number of Deaths due to Japanese Encephalitis (JE)
16.9. :: Total Deaths (5 years and above of age): Excluding in-transit & maternal deaths
16.9.1. :: 5 years and above to below 10 years
16.9.2. :: 10 year and above to below 19 years
16.9.3. :: Adult 19 years and above
16.10.1. :: In-transit Deaths: 1 year and below 5 years
16.10.2. :: In-transit Deaths: 5 years and above to below 10 years
16.10.3. :: In-transit Deaths: 10 year and above to below 19 years
16.10.4. :: In-transit Deaths: Adult 19 years and above
17.1.1. :: Total number of Haematology tests registered under External Quality Assurance Scheme (EQAS)
17.1.2. :: No. of registered Haematology tests reported EQAS Compliant
17.1.3. :: Total number of Biochemistry tests registered under External Quality Assurance Scheme (EQAS)
17.1.4. :: No. of registered Bio chemistry tests report EQAS Compliant
17.1.5. :: Total Quantity of Bio medical waste generated in Kg for the month - (All Yellow, Red, white & Blue)
17.1.6. :: Total Quantity of General waste generated in Kg for the month
17.2.1. :: Total number of breakdown calls reported for the month
17.2.2. :: Total number of breakdown attended for the month
17.2.3. :: Number of visit made by the service engineer/ BME for the month
"""
ALL_METRICS_LIST = [m.strip() for m in RAW_METRICS.strip().split('\n') if m.strip()]

# --- INITIALIZE DUCKDB DATABASE ---
@st.cache_resource
def init_db():
    con = duckdb.connect("hmis_database.duckdb")  
    con.execute("""
        CREATE TABLE IF NOT EXISTS hmis_master_data (
            Financial_Year VARCHAR, Month VARCHAR, District_Name VARCHAR,
            Format_Type VARCHAR, Facility_Code VARCHAR, Facility_Name VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS rules_metadata_v3 (
            Category_Code VARCHAR, Rule_ID VARCHAR, Rule_Description VARCHAR,
            Target_Format VARCHAR, Rule_Type VARCHAR, Logic_LHS VARCHAR, 
            Operator VARCHAR, Logic_RHS VARCHAR, Show_Difference BOOLEAN
        )
    """)
    
    # --- STEP 1: DATABASE AUTO-MIGRATION FOR DIMENSIONS & MOM PATTERNS ---
    try:
        existing_cols = [row[1] for row in con.execute("PRAGMA table_info('rules_metadata_v3')").fetchall()]
        schema_additions = {
            "Rule_Category": "VARCHAR DEFAULT 'Single Month'",
            "Trend_Pattern": "VARCHAR DEFAULT 'None'",
            "PHC_Area_Scope": "VARCHAR DEFAULT 'All'",
            "Non_PHC_Ownership": "VARCHAR DEFAULT 'All'",
            "Trend_Window_Months": "INTEGER DEFAULT 3",
            "Trend_Threshold": "FLOAT DEFAULT 3.0"
        }
        for col_name, col_def in schema_additions.items():
            if col_name not in existing_cols:
                con.execute(f"ALTER TABLE rules_metadata_v3 ADD COLUMN {col_name} {col_def}")
    except Exception as e:
        pass
        
    # Create table for secure admin settings
    con.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            setting_name VARCHAR, setting_value VARCHAR
        )
    """)
    
    # Insert default password if it doesn't exist yet
    pw_exists = con.execute("SELECT * FROM admin_settings WHERE setting_name = 'admin_password'").fetchone()
    if not pw_exists:
        con.execute("INSERT INTO admin_settings VALUES ('admin_password', 'admin123')")
        
    return con

con = init_db()

# --- SIDEBAR: MASTER FILTERS ---
st.sidebar.header("🔍 Global Filters")
financial_year = st.sidebar.selectbox("Financial Year", ["2026-27"])

# Extract dynamic lists from the Database
try:
    db_months = con.execute("SELECT DISTINCT Month FROM hmis_master_data WHERE Month IS NOT NULL").fetchdf()['Month'].tolist()
    
    # --- THE FIX: Look for "District Name" with a space, using double quotes for SQL ---
    db_districts = con.execute('SELECT DISTINCT "District Name" FROM hmis_master_data WHERE "District Name" IS NOT NULL').fetchdf()['District Name'].tolist()
    
except Exception as e:
    db_months, db_districts = [], []

month_list = ["All Months"] + db_months if db_months else ["All Months", "Apr-2026", "May-2026", "Jun-2026", "Jul-2026", "Aug-2026", "Sep-2026"]
district_list = ["All Districts"] + sorted(db_districts) if db_districts else ["All Districts", "Anakapalli", "Eluru", "Kakinada", "Nandyal"]

selected_month = st.sidebar.selectbox("Reporting Month", month_list)
selected_district = st.sidebar.selectbox("District Name", district_list)
facility_code = st.sidebar.text_input("Facility Code", placeholder="e.g., 44151234")

col_empty, col_btn = st.sidebar.columns([2, 1.5])
with col_btn:
    search_triggered = st.button("🔍 Search", use_container_width=True)

if search_triggered:
    st.sidebar.success("Filters applied globally!")

# --- SECURE ADMIN ACCESS ---
st.sidebar.markdown("---")
admin_password = st.sidebar.text_input("🔒 Admin Access", type="password", help="Enter master password to unlock Admin tab")

# Fetch current password directly from the database
try:
    current_db_password = con.execute("SELECT setting_value FROM admin_settings WHERE setting_name = 'admin_password'").fetchone()[0]
except:
    current_db_password = "admin" # Failsafe just in case table is empty

is_admin = (admin_password == current_db_password)

# --- 🚀 ENTERPRISE CACHING LAYER (Solves the 1,000 User Bottleneck) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_hmis_data(sel_fy):
    """Fetches the entire FY once and shares it across all 1,000 users in RAM."""
    try:
        return con.execute("SELECT * FROM hmis_master_data WHERE Financial_Year = ?", [sel_fy]).fetchdf()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_rules():
    """Caches the rules dictionary to prevent database locking."""
    try:
        return con.execute("SELECT * FROM rules_metadata_v3").fetchdf()
    except:
        return pd.DataFrame()

# --- MASTER EXECUTION ENGINE: REAL DATA BINDING ---
def run_anomaly_engine(sel_fy, sel_month, sel_dist, fac_code):
    import re
    import pandas as pd
    
    # 1. Pull from the blazing fast memory cache instead of hitting the database!
    full_fy_df = get_cached_hmis_data(sel_fy)
    rules_df = get_cached_rules()
    
    if full_fy_df.empty or rules_df.empty:
        return pd.DataFrame()
        
    # 2. Filter the cached data IN MEMORY for the Single Month Engine
    # (The full_fy_df remains intact in memory for the MoM engine to use later)
    raw_df = full_fy_df.copy()
    
    if sel_month != "All Months":
        raw_df = raw_df[raw_df['Month'] == sel_month]
    if sel_dist != "All Districts":
        raw_df = raw_df[raw_df['District Name'] == sel_dist]
    if fac_code:
        raw_df = raw_df[raw_df['Facility Code'].astype(str) == str(fac_code)]
        
    anomalies = []
    
    for _, rule in rules_df.iterrows():
        r_id = rule['Rule_ID']
        r_desc = rule['Rule_Description']
        
        # Bridge the old 'Math' type with the new 'Single Month' category
        r_type = rule.get('Rule_Category', rule.get('Rule_Type', 'Math')) 
        
        t_format = str(rule['Target_Format'])
        lhs_raw = str(rule['Logic_LHS'])
        op = str(rule['Operator'])
        rhs_raw = str(rule['Logic_RHS'])
        
        # --- ONLY PROCESS SINGLE MONTH RULES FOR THE MAIN DASHBOARD ---
        if r_type == 'Math' or r_type == 'Single Month':
            df_eval = raw_df.copy()
            
            if "All Formats" not in t_format:
                formats = [f.strip() for f in t_format.split(',')]
                df_eval = df_eval[df_eval['Format Type'].isin(formats)]
                
            # --- DIMENSIONAL FILTERING (STEP 3 - LOCATION 2) ---
            phc_scope = str(rule.get('PHC_Area_Scope', 'All'))
            non_phc_own = str(rule.get('Non_PHC_Ownership', 'All'))
            
            if phc_scope in ['Rural', 'Urban']:
                phc_mask = df_eval['Format Type'] == 'PHC Format'
                if 'Rural/Urban' in df_eval.columns:
                    ru_match = df_eval['Rural/Urban'].astype(str).str.strip().str.upper() == phc_scope.upper()
                    df_eval = df_eval[(~phc_mask) | (phc_mask & ru_match)]
                    
            if non_phc_own in ['Public', 'Private']:
                non_phc_mask = df_eval['Format Type'] != 'PHC Format'
                if 'Ownership' in df_eval.columns:
                    own_match = df_eval['Ownership'].astype(str).str.strip().str.upper() == non_phc_own.upper()
                    df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & own_match)]
                elif 'Facility Name' in df_eval.columns:
                    is_pvt = df_eval['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False)
                    target_match = is_pvt if non_phc_own == 'Private' else ~is_pvt
                    df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & target_match)]
            # ---------------------------------------------------
            
            if df_eval.empty:
                continue
            
            metrics = list(set(re.findall(r'\[(.*?)\]', lhs_raw + " " + rhs_raw)))
            
            # Convert ONLY the required metrics to numbers safely
            for m in metrics:
                if m in df_eval.columns:
                    df_eval[m] = pd.to_numeric(df_eval[m], errors='coerce').fillna(0)
            
            missing = [m for m in metrics if m not in df_eval.columns]
            
            if not missing:
                eval_lhs, eval_rhs = lhs_raw, rhs_raw
                for m in metrics:
                    eval_lhs = eval_lhs.replace(f"[{m}]", f"`{m}`")
                    eval_rhs = eval_rhs.replace(f"[{m}]", f"`{m}`")
                
                try:
                    eval_op = "==" if op == "=" else ("!=" if op == "<>" else op)
                    eval_str = f"({eval_lhs}) {eval_op} ({eval_rhs})"
                    
                    mask = df_eval.eval(eval_str)
                    failed_rows = df_eval[mask]
                    
                    for _, row in failed_rows.iterrows():
                        anomalies.append({
                            "Month": row['Month'],
                            "District Name": row['District Name'],
                            "Format Type": row['Format Type'],
                            "Facility Code": row['Facility Code'],
                            "Facility Name": row['Facility Name'],
                            "Rule_ID": r_id,
                            "Anomaly Type": r_desc,
                            "Error Count": 1
                        })
                except Exception as e:
                    pass
                    
    return pd.DataFrame(anomalies)

# Run the engine instantly when filters change!
df_anomalies = run_anomaly_engine(financial_year, selected_month, selected_district, facility_code)

# 3. Aggregate Engine Output for Dashboard Visuals
if not df_anomalies.empty:
    df_dist_filtered = df_anomalies.groupby('District Name')['Error Count'].sum().reset_index().sort_values(by="Error Count", ascending=True)
    facilities_count = df_anomalies['Facility Code'].nunique()
    anomaly_types_count = df_anomalies['Anomaly Type'].nunique()
    total_anomalies_calc = df_anomalies['Error Count'].sum()
    df_top_rules = df_anomalies.groupby('Anomaly Type')['Error Count'].sum().reset_index().sort_values(by='Error Count', ascending=False)
    
    df_abstract_final = df_top_rules.rename(columns={'Error Count': 'Anomaly Count'})
    df_fac_final = df_anomalies.copy()
else:
    df_dist_filtered = pd.DataFrame(columns=["District Name", "Error Count"])
    df_top_rules = pd.DataFrame(columns=["Anomaly Type", "Error Count"])
    df_abstract_final = pd.DataFrame(columns=["Anomaly Type", "Anomaly Count"])
    df_fac_final = pd.DataFrame(columns=["Month", "District Name", "Format Type", "Facility Code", "Facility Name", "Anomaly Type", "Error Count"])
    facilities_count = 0
    anomaly_types_count = 0
    total_anomalies_calc = 0
    
pub_val, priv_val = 95.4, 4.6 # Static placeholder until ownership mapping is added

# --- TOP HEADER BANNER ---
st.markdown('<div class="ds-yellow-header">HMIS DATA VALIDATION DASHBOARD, ANDHRA PRADESH</div>', unsafe_allow_html=True)
st.write("") # spacer

# --- MoM TREND EXECUTION ENGINE ---
def run_trend_engine(sel_fy, sel_dist, fac_code):
    import pandas as pd
    
    full_fy_df = get_cached_hmis_data(sel_fy).copy()
    rules_df = get_cached_rules()
    
    if full_fy_df.empty or rules_df.empty:
        return pd.DataFrame()
        
    mom_rules = rules_df[rules_df['Rule_Category'] == 'MoM Trend']
    if mom_rules.empty:
        return pd.DataFrame()
        
    # 1. STRICT TIME-SERIES PREP (Chronological Ordering)
    full_fy_df['Date_Parsed'] = pd.to_datetime(full_fy_df['Month'], format='%b-%Y', errors='coerce')
    full_fy_df = full_fy_df.sort_values(by=['Facility Code', 'Date_Parsed'])
    
    if sel_dist != "All Districts":
        full_fy_df = full_fy_df[full_fy_df['District Name'] == sel_dist]
    if fac_code:
        full_fy_df = full_fy_df[full_fy_df['Facility Code'].astype(str) == str(fac_code)]
        
    trend_anomalies = []
    
    for _, rule in mom_rules.iterrows():
        r_id = rule['Rule_ID']
        r_desc = rule['Rule_Description']
        pattern = str(rule['Trend_Pattern'])
        t_format = str(rule['Target_Format'])
        window = int(rule.get('Trend_Window_Months', 1))
        threshold = float(rule.get('Trend_Threshold', 0.0))
        
        df_eval = full_fy_df.copy()
        
        # --- DIMENSIONAL FILTERING ---
        phc_scope = str(rule.get('PHC_Area_Scope', 'All'))
        non_phc_own = str(rule.get('Non_PHC_Ownership', 'All'))
        
        if "All Formats" not in t_format:
            formats = [f.strip() for f in t_format.split(',')]
            df_eval = df_eval[df_eval['Format Type'].isin(formats)]
            
        if phc_scope in ['Rural', 'Urban']:
            phc_mask = df_eval['Format Type'] == 'PHC Format'
            if 'Rural/Urban' in df_eval.columns:
                ru_match = df_eval['Rural/Urban'].astype(str).str.strip().str.upper() == phc_scope.upper()
                df_eval = df_eval[(~phc_mask) | (phc_mask & ru_match)]
                
        if non_phc_own in ['Public', 'Private']:
            non_phc_mask = df_eval['Format Type'] != 'PHC Format'
            if 'Ownership' in df_eval.columns:
                own_match = df_eval['Ownership'].astype(str).str.strip().str.upper() == non_phc_own.upper()
                df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & own_match)]
            elif 'Facility Name' in df_eval.columns:
                is_pvt = df_eval['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False)
                target_match = is_pvt if non_phc_own == 'Private' else ~is_pvt
                df_eval = df_eval[(~non_phc_mask) | (non_phc_mask & target_match)]
                
        if df_eval.empty: continue

        # --- PATTERN 1: SUDDEN SPIKES ---
        if "Sudden Spike" in pattern:
            target_metric = str(rule['Logic_LHS']).strip('[]')
            if target_metric in df_eval.columns:
                df_eval[target_metric] = pd.to_numeric(df_eval[target_metric], errors='coerce').fillna(0)
                
                # Window Function: Calculate historical average EXCLUDING the current month
                df_eval['Historical_Avg'] = df_eval.groupby('Facility Code')[target_metric].transform(
                    lambda x: x.shift(1).rolling(window, min_periods=1).mean()
                )
                
                # Flag Spike: Current > (Historical Avg * Multiplier)
                mask = (df_eval[target_metric] > (df_eval['Historical_Avg'] * threshold)) & (df_eval['Historical_Avg'] > 0)
                failed_rows = df_eval[mask]
                
                for _, row in failed_rows.iterrows():
                    trend_anomalies.append({
                        "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                        "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                        "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Spike", 
                        "Details": f"Value {row[target_metric]} is {threshold}x higher than historical avg {round(row['Historical_Avg'], 1)}"
                    })
                    
        # --- PATTERN 2: REPEATED CONSTANTS (FLATLINES) ---
        elif "Repeated Constant" in pattern:
            target_metric = str(rule['Logic_LHS']).strip('[]')
            if target_metric in df_eval.columns:
                df_eval[target_metric] = pd.to_numeric(df_eval[target_metric], errors='coerce').fillna(0)
                
                # Window Function: Check if the value hasn't changed over X months
                df_eval['Rolling_Min'] = df_eval.groupby('Facility Code')[target_metric].transform(lambda x: x.rolling(window).min())
                df_eval['Rolling_Max'] = df_eval.groupby('Facility Code')[target_metric].transform(lambda x: x.rolling(window).max())
                
                # Flag Flatline: The Max and Min of the last X months are exactly the same, and value is > 0
                mask = (df_eval['Rolling_Min'] == df_eval['Rolling_Max']) & (df_eval[target_metric] > 0)
                failed_rows = df_eval[mask]
                
                for _, row in failed_rows.iterrows():
                    trend_anomalies.append({
                        "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                        "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                        "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Flatline", 
                        "Details": f"Value {row[target_metric]} copy-pasted for {window} consecutive months"
                    })

        # --- PATTERN 3: CATEGORY SHIFT (ZERO-TO-MAX) ---
        elif "Category Shift" in pattern:
            import re
            metrics = re.findall(r'\[(.*?)\]', str(rule['Logic_LHS']))
            if len(metrics) == 2:
                sub_metric, tot_metric = metrics[0], metrics[1]
                if sub_metric in df_eval.columns and tot_metric in df_eval.columns:
                    df_eval[sub_metric] = pd.to_numeric(df_eval[sub_metric], errors='coerce').fillna(0)
                    df_eval[tot_metric] = pd.to_numeric(df_eval[tot_metric], errors='coerce').fillna(0)
                    
                    # Window Function: Look back to see if sub_metric was consistently 0
                    df_eval['Hist_Max'] = df_eval.groupby('Facility Code')[sub_metric].transform(
                        lambda x: x.shift(1).rolling(window, min_periods=1).max()
                    )
                    
                    # Current month ratio against the parent total
                    df_eval['Current_Share'] = (df_eval[sub_metric] / df_eval[tot_metric].replace(0, 1)) * 100
                    
                    # Flag: History was 0, but current share is >= the threshold
                    mask = (df_eval['Hist_Max'] == 0) & (df_eval['Current_Share'] >= threshold) & (df_eval[tot_metric] > 0)
                    failed_rows = df_eval[mask]
                    
                    for _, row in failed_rows.iterrows():
                        trend_anomalies.append({
                            "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                            "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                            "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Category Shift",
                            "Details": f"Historically 0, but suddenly jumped to {round(row['Current_Share'], 1)}% of total ({row[sub_metric]}/{row[tot_metric]})"
                        })

        # --- PATTERN 4: MULTI-INDICATOR COPY-PASTE ---
        elif "Copy-Paste" in pattern:
            import re
            metrics = list(set(re.findall(r'\[(.*?)\]', str(rule['Logic_LHS']))))
            valid_metrics = [m for m in metrics if m in df_eval.columns]
            
            if len(valid_metrics) > 1:
                for m in valid_metrics:
                    df_eval[m] = pd.to_numeric(df_eval[m], errors='coerce').fillna(0)
                
                # Check if all targeted metrics have the exact same value in the row
                df_eval['Min_Val'] = df_eval[valid_metrics].min(axis=1)
                df_eval['Max_Val'] = df_eval[valid_metrics].max(axis=1)
                
                # Flag: Min == Max (meaning all are mathematically identical) AND value is not 0
                mask = (df_eval['Min_Val'] == df_eval['Max_Val']) & (df_eval['Max_Val'] > 0)
                failed_rows = df_eval[mask]
                
                for _, row in failed_rows.iterrows():
                    val = row['Max_Val']
                    trend_anomalies.append({
                        "Month": row['Month'], "District Name": row['District Name'], "Format Type": row['Format Type'],
                        "Facility Code": row['Facility Code'], "Facility Name": row['Facility Name'],
                        "Rule_ID": r_id, "Anomaly Type": r_desc, "Pattern": "Copy-Paste",
                        "Details": f"Value {val} was copy-pasted across {len(valid_metrics)} different indicators"
                    })

    return pd.DataFrame(trend_anomalies)

# --- DYNAMIC MULTI-TAB ARCHITECTURE ---
public_tab_names = [
    "📊 HMIS Dash Board",           # Index 0 -> tab1
    "📑 Single Month Anomalies",    # Index 1 -> tab2
    "📈 MoM Trend Anomalies",       # Index 2 -> tab_mom
    "📜 Rules Dictionary",          # Index 3 -> tab5
    "📖 Indicators List"            # Index 4 -> tab6
]

admin_tab_names = [
    "🏥 Facility wise anomalies",   # Index 5 -> tab3
    "🎯 Detailed Anomalies",        # Index 6 -> tab4
    "⚙️ Admin"                      # Index 7 -> tab7
]

# Build the final list based on login status
tab_names = public_tab_names.copy()
if is_admin:
    tab_names.extend(admin_tab_names)

tabs = st.tabs(tab_names)

# Map variables securely so existing code doesn't crash
tab1, tab2, tab_mom, tab5, tab6 = tabs[0], tabs[1], tabs[2], tabs[3], tabs[4]

if is_admin:
    tab3, tab4, tab7 = tabs[5], tabs[6], tabs[7]

# --- RUN THE MASTER EXECUTION ENGINE ---
# This engine evaluates ALL rules against the uploaded data based on sidebar filters
master_anomalies_df = run_anomaly_engine(financial_year, selected_month, selected_district, facility_code)

# --- SHARED TABLE STYLING FOR ALL TABS ---
shared_custom_css = {
    ".ag-header-cell-text": {"font-size": "14px", "font-weight": "900", "color": "#004085"},
    ".ag-header-cell-label": {"justify-content": "center"},
    ".ag-header-cell": {"border-right": "1px solid #dee2e6"}
}

shared_cell_style = {
    'textAlign': 'center', 'backgroundColor': '#ffffff', 'color': '#000000',
    'fontSize': '14px', 'fontWeight': 'bold', 
    'borderRight': '1px solid #dee2e6', 'borderBottom': '1px solid #dee2e6'
}

# Helper function to configure all grids identically
def build_grid_options(df):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        wrapHeaderText=True, 
        autoHeaderHeight=True, 
        resizable=True, 
        wrapText=True, 
        autoHeight=True, 
        sortable=True, 
        filter=False,           
        suppressMenu=True,      
        cellStyle=shared_cell_style
    )
    gridOptions = gb.build()
    gridOptions['suppressMenuHide'] = True
    return gridOptions

# --- THE ULTIMATE POPUP DRILL-DOWN MODAL ---
@st.dialog("🔍 Deep-Dive Analysis Mode", width="large")
def show_drilldown_modal(selected_anomaly, raw_df, financial_year, selected_month, selected_district, facility_code):
    import re
    
    st.markdown(f"<h4 style='color: #d32f2f; margin-top: -10px; margin-bottom: 20px;'>{selected_anomaly}</h4>", unsafe_allow_html=True)
    
    try:
        rule_info_df = con.execute("SELECT * FROM rules_metadata_v3 WHERE Rule_Description = ?", [selected_anomaly]).fetchdf()
        if rule_info_df.empty:
            st.error("Rule metadata missing.")
            return
            
        rule_info = rule_info_df.iloc[0]
        lhs_raw, rhs_raw, op, t_format = str(rule_info['Logic_LHS']), str(rule_info['Logic_RHS']), str(rule_info['Operator']), str(rule_info['Target_Format'])
        all_metrics_raw = re.findall(r'\[(.*?)\]', lhs_raw) + re.findall(r'\[(.*?)\]', rhs_raw)
        metrics_in_rule = list(dict.fromkeys(all_metrics_raw))
        
        if not raw_df.empty:
            for m in metrics_in_rule:
                if m in raw_df.columns:
                    raw_df[m] = pd.to_numeric(raw_df[m], errors='coerce').fillna(0)
            
            # --- THE DIMENSIONAL FILTERING (STEP 3) ---
            phc_scope = str(rule_info.get('PHC_Area_Scope', 'All'))
            non_phc_own = str(rule_info.get('Non_PHC_Ownership', 'All'))
            
            if "All Formats" not in t_format:
                formats = [f.strip() for f in t_format.split(',')]
                raw_df = raw_df[raw_df['Format Type'].isin(formats)]
                
            if phc_scope in ['Rural', 'Urban']:
                phc_mask = raw_df['Format Type'] == 'PHC Format'
                if 'Rural/Urban' in raw_df.columns:
                    ru_match = raw_df['Rural/Urban'].astype(str).str.strip().str.upper() == phc_scope.upper()
                    raw_df = raw_df[(~phc_mask) | (phc_mask & ru_match)]
                    
            if non_phc_own in ['Public', 'Private']:
                non_phc_mask = raw_df['Format Type'] != 'PHC Format'
                if 'Ownership' in raw_df.columns:
                    own_match = raw_df['Ownership'].astype(str).str.strip().str.upper() == non_phc_own.upper()
                    raw_df = raw_df[(~non_phc_mask) | (non_phc_mask & own_match)]
                elif 'Facility Name' in raw_df.columns:
                    is_pvt = raw_df['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False)
                    target_match = is_pvt if non_phc_own == 'Private' else ~is_pvt
                    raw_df = raw_df[(~non_phc_mask) | (non_phc_mask & target_match)]
            # ------------------------------------------

            eval_lhs, eval_rhs = lhs_raw, rhs_raw
            for m in metrics_in_rule:
                eval_lhs, eval_rhs = eval_lhs.replace(f"[{m}]", f"`{m}`"), eval_rhs.replace(f"[{m}]", f"`{m}`")
            
            eval_op = "==" if op == "=" else ("!=" if op == "<>" else op)
            eval_str = f"({eval_lhs}) {eval_op} ({eval_rhs})"
            
            mask = raw_df.eval(eval_str)
            detailed_df = raw_df[mask].copy()
            
            if not detailed_df.empty:
                detailed_df['LHS Value'] = detailed_df.eval(eval_lhs)
                detailed_df['RHS Value'] = detailed_df.eval(eval_rhs)
                detailed_df['Difference (LHS - RHS)'] = detailed_df['LHS Value'] - detailed_df['RHS Value']
                
                base_cols = ["Month", "District Name", "Format Type", "Facility Code", "Facility Name"]
                display_cols = [c for c in base_cols if c in detailed_df.columns] + metrics_in_rule + ['Difference (LHS - RHS)']
                
                drill_final = detailed_df[display_cols].copy()
                drill_final.insert(0, 'S.No', range(1, len(drill_final) + 1))
                
                # --- MODAL KPI CARDS ---
                mk1, mk2, mk3 = st.columns(3)
                mk_style = "background-color: #f8f9fa; border-left: 4px solid #ff5722; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 15px;"
                with mk1: st.markdown(f'<div style="{mk_style}"><div style="font-size:12px; color:#555;">Total Errors</div><div style="font-size:22px; font-weight:bold; color:#d32f2f;">{len(drill_final):,}</div></div>', unsafe_allow_html=True)
                with mk2: st.markdown(f'<div style="{mk_style}"><div style="font-size:12px; color:#555;">Affected Facilities</div><div style="font-size:22px; font-weight:bold; color:#1976d2;">{drill_final["Facility Code"].nunique():,}</div></div>', unsafe_allow_html=True)
                with mk3: st.markdown(f'<div style="{mk_style}"><div style="font-size:12px; color:#555;">Affected Districts</div><div style="font-size:22px; font-weight:bold; color:#388e3c;">{drill_final["District Name"].nunique():,}</div></div>', unsafe_allow_html=True)

                # --- RENDER GRID IN MODAL ---
                gridOptions_drill = build_grid_options(drill_final)
                for col in gridOptions_drill['columnDefs']:
                    if col['field'] == 'S.No': col['width'], col['pinned'], col['filter'] = 70, 'left', False
                    elif col['field'] not in base_cols: col['filter'] = False
                        
                AgGrid(drill_final, gridOptions=gridOptions_drill, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=False, height=400, key="modal_grid")
                
                # DOWNLOAD INSIDE MODAL
                csv_drill = drill_final.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Detailed Report", data=csv_drill, file_name="Anomaly_Deep_Dive.csv", mime="text/csv", type="primary", use_container_width=True)
            else:
                st.info("No detailed data found for this rule under current filters.")
    except Exception as e:
        st.error(f"Error generating detailed view: {e}")

# =====================================================================
# TAB 1: HMIS DASHBOARD (Advanced State-Level Metrics & Charts)
# =====================================================================
with tab1:
        if not master_anomalies_df.empty:
            anomaly_types_count = master_anomalies_df['Rule_ID'].nunique()
            facilities_count = master_anomalies_df['Facility Code'].nunique()
            total_anomalies_calc = len(master_anomalies_df)
            
            df_dist_filtered = master_anomalies_df.groupby('District Name').size().reset_index(name='Error Count')
            df_top_rules = master_anomalies_df.groupby('Anomaly Type').size().reset_index(name='Error Count').sort_values(by='Error Count', ascending=False)
            
            if 'Facility Name' in master_anomalies_df.columns:
                priv_val = int(master_anomalies_df['Facility Name'].str.contains('Private|Pvt|Trust|NGO', case=False, na=False).sum())
                pub_val = total_anomalies_calc - priv_val
            else:
                pub_val, priv_val = total_anomalies_calc, 0
        else:
            anomaly_types_count = 0
            facilities_count = 0
            total_anomalies_calc = 0
            df_dist_filtered = pd.DataFrame({"District Name": ["No Data"], "Error Count": [0]})
            df_top_rules = pd.DataFrame({"Anomaly Type": ["No Errors"], "Error Count": [0]})
            pub_val, priv_val = 1, 0

        error_density = round(total_anomalies_calc / facilities_count, 1) if facilities_count > 0 else 0

        # 4-Tile State-Level Metrics Layout
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #d32f2f;"><div class="kpi-title">Total Anomalies</div><div class="kpi-value">{total_anomalies_calc:,}</div><div style="color: #d32f2f; font-size: 14px; font-weight: bold;">🔼 Live Engine Count</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #ff9800;"><div class="kpi-title">Facilities With Errors</div><div class="kpi-value">{facilities_count:,}</div><div style="color: #6c757d; font-size: 14px;">Requiring Intervention</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #1976d2;"><div class="kpi-title">Error Density</div><div class="kpi-value">{error_density}</div><div style="color: #6c757d; font-size: 14px;">Avg Errors per Facility</div></div>', unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="kpi-tile" style="border-top: 5px solid #9c27b0;"><div class="kpi-title">Rules Triggered</div><div class="kpi-value">{anomaly_types_count}</div><div style="color: #6c757d; font-size: 14px;">Unique Logic Failures</div></div>', unsafe_allow_html=True)
            
        st.divider()
        col_chart1, col_chart2 = st.columns([1.5, 1])
        
        with col_chart1:
            st.markdown('<div class="chart-title">DISTRICT WISE ANOMALIES HEAT MAP</div>', unsafe_allow_html=True)
            fig_bar = px.bar(df_dist_filtered, x="Error Count", y="District Name", orientation='h', color_discrete_sequence=['#4285F4'], text="Error Count")
            fig_bar.update_traces(textposition='inside', insidetextanchor='middle', textangle=0, textfont=dict(size=18, color='white', family="Arial Black"))
            
            # Allow the chart inside the container to expand as needed
            chart_height = max(380, len(df_dist_filtered) * 35) 
            fig_bar.update_layout(yaxis=dict(categoryorder='total ascending', tickfont=dict(size=14, color='black', family="Arial Black")), height=chart_height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            
            # Wrap in fixed container (430px) to force scrolling instead of stretching the page
            with st.container(height=400):
                st.plotly_chart(fig_bar, use_container_width=True)
                
            st.markdown(f'<div style="background-color: #ff9800; color: #000; font-weight: 900; font-size: 16px; padding: 12px; border-radius: 5px; display: flex; justify-content: space-between; margin-top: 10px;"><span>Grand total</span><span>{total_anomalies_calc:,}</span></div>', unsafe_allow_html=True)

        with col_chart2:
            st.markdown('<div class="chart-title">PUBLIC / PRIVATE %</div>', unsafe_allow_html=True)
            fig_pie = px.pie(pd.DataFrame({"Sector": ["Public", "Private"], "Value": [pub_val, priv_val]}), values='Value', names='Sector', color_discrete_sequence=['#4285F4', '#FF9900'])
            
            # Constrain pie chart to 180px
            fig_pie.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', legend=dict(font=dict(size=14, color="#333", family="Arial Black")))
            fig_pie.update_traces(textposition='inside', textinfo='percent', textfont=dict(size=15, color='white', family="Arial Black"))
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.markdown('<div class="chart-title" style="margin-top: 10px;">TOP 10 ANOMALIES</div>', unsafe_allow_html=True)
            
            if total_anomalies_calc > 0 and not df_top_rules.empty:
                import textwrap
                top_10 = df_top_rules.head(10).copy()
                
                # 1. Shorten name for the clean legend
                top_10['Short Rule'] = top_10['Anomaly Type'].apply(lambda x: str(x).split(" ")[0] if "-" in str(x) else str(x)[:15])
                
                # 2. Use Textwrap to force line-breaks (<br>) every 45 characters for the hover box
                top_10['Wrapped_Anomaly'] = top_10['Anomaly Type'].apply(lambda x: '<br>'.join(textwrap.wrap(str(x), width=45)))
                
                fig_donut = px.pie(top_10, values='Error Count', names='Short Rule', hole=0.5, custom_data=['Wrapped_Anomaly'])
                
                # 3. Inject the beautifully wrapped text into the hover popup
                fig_donut.update_traces(
                    hovertemplate="<b style='font-size:13px;'>%{customdata[0]}</b><br><br><b>Errors:</b> %{value}<br><b>Share:</b> %{percent}<extra></extra>",
                    hoverlabel=dict(align="left", font=dict(size=13)),
                    textposition='inside', textinfo='percent', textfont=dict(size=13, color='white', family="Arial Black")
                )
            else:
                fig_donut = px.pie(pd.DataFrame({"Anomaly Type": ["No Errors"], "Error Count": [1]}), values='Error Count', names='Anomaly Type', hole=0.5)
                fig_donut.update_traces(textinfo='none')
            
            # Constrain donut chart to 230px (Total right side matches left container perfectly)
            fig_donut.update_layout(
                height=210, 
                margin=dict(l=0, r=0, t=10, b=10), 
                paper_bgcolor='rgba(0,0,0,0)', 
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0, font=dict(size=12, color="#333", family="Arial Black"))
            )
            st.plotly_chart(fig_donut, use_container_width=True)


# =====================================================================
# TAB 2: ANOMALIES ABSTRACT & POPUP DRILL-DOWN
# =====================================================================
with tab2:
        st.markdown("""
            <style>
            @keyframes sparkle-animation {
                0% { color: #D32F2F; text-shadow: 0 0 4px rgba(211, 47, 47, 0.6); transform: scale(1); }
                50% { color: #00B0FF; text-shadow: 0 0 10px #00B0FF, 0 0 20px #40C4FF; transform: scale(1.02); }
                100% { color: #D32F2F; text-shadow: 0 0 4px rgba(211, 47, 47, 0.6); transform: scale(1); }
            }
            .animated-instruction { font-size: 24px; font-weight: 900; animation: sparkle-animation 1.5s ease-in-out infinite; margin-left: 15px; }
            .header-wrapper { font-size: 26px; font-weight: bold; margin-bottom: 20px; display: flex; align-items: center; border-bottom: 2px solid #eeeeee; padding-bottom: 10px; }
            </style>
            
            <div class="header-wrapper">
                📄 Anomalies Abstract Table: 
                <span class="animated-instruction">👉 Click On Required Anomaly to get Detailed Report</span>
            </div>
        """, unsafe_allow_html=True)
        
        if not master_anomalies_df.empty:
            abstract_df = master_anomalies_df.groupby('Anomaly Type').size().reset_index(name='Anomaly Count').sort_values(by='Anomaly Count', ascending=False)
            abstract_df.insert(0, 'Sl No', range(1, len(abstract_df) + 1))
            
            csv_data = abstract_df.to_csv(index=False).encode('utf-8')
            col_spacer, col_dl = st.columns([5, 1.5])
            with col_dl:
                st.download_button("📥 Download Abstract to CSV", data=csv_data, file_name="Abstract_Anomalies.csv", mime="text/csv", type="primary", use_container_width=True, key="dl_abs")
            
            gridOptions_abs = build_grid_options(abstract_df)
            gridOptions_abs['rowSelection'] = 'single'
            
            for col in gridOptions_abs['columnDefs']:
                if col['field'] == 'Sl No': col['width'], col['maxWidth'], col['pinned'], col['filter'], col['suppressSizeToFit'] = 80, 80, 'left', False, True
                elif col['field'] == 'Anomaly Count': col['width'], col['maxWidth'], col['filter'], col['suppressSizeToFit'] = 150, 150, False, True
                elif col['field'] == 'Anomaly Type': col['flex'], col['wrapText'], col['autoHeight'] = 1, True, True
            
            tab2_css = shared_custom_css.copy() if 'shared_custom_css' in locals() else {}
            tab2_css[".ag-row-selected .ag-cell"] = {"background-color": "#FFB74D !important", "color": "#000000 !important", "font-weight": "bold !important"}
            tab2_css[".ag-row-selected"] = {"border-bottom": "2px solid #E65100 !important"}
            
            response = AgGrid(abstract_df, gridOptions=gridOptions_abs, theme='alpine', custom_css=tab2_css, fit_columns_on_grid_load=True, height=450, update_mode="SELECTION_CHANGED", key="abstract_main_grid")
            
            # --- TAB 2: GRAND TOTAL BAR ---
            tab2_total = abstract_df['Anomaly Count'].sum()
            st.markdown(f'<div style="background-color: #ff9800; color: #000; font-weight: 900; font-size: 16px; padding: 12px; border-radius: 5px; display: flex; justify-content: space-between; margin-top: 10px;"><span>Grand Total Anomalies</span><span>{tab2_total:,}</span></div>', unsafe_allow_html=True)
            
            # --- TRIGGER POPUP MODAL ON ROW CLICK (WITH ANTI-HAUNTING LOCK) ---
            sel_rows = response.get('selected_rows')
            
            if sel_rows is not None and len(sel_rows) > 0:
                selected_val = sel_rows.iloc[0]['Anomaly Type'] if isinstance(sel_rows, pd.DataFrame) else sel_rows[0]['Anomaly Type']
                
                # THE ANTI-HAUNTING LOCK: Only trigger if this specific anomaly hasn't just been opened
                if st.session_state.get('modal_anomaly_lock') != selected_val:
                    st.session_state['modal_anomaly_lock'] = selected_val
                    
                    query = "SELECT * FROM hmis_master_data WHERE Financial_Year = ?"
                    params = [financial_year]
                    if selected_month != "All Months": query += " AND Month = ?"; params.append(selected_month)
                    if selected_district != "All Districts": query += ' AND "District Name" = ?'; params.append(selected_district)
                    if facility_code: query += ' AND "Facility Code" = ?'; params.append(facility_code)
                    
                    raw_df_modal = con.execute(query, params).fetchdf()
                    show_drilldown_modal(selected_val, raw_df_modal, financial_year, selected_month, selected_district, facility_code)
            else:
                # Clear the lock if they unclick the row, so they can click it again later if they want
                st.session_state['modal_anomaly_lock'] = None
                
        else:
            st.success("✅ No anomalies found for the selected criteria. The Abstract is clear.")

# =====================================================================
# TAB 3: MoM TREND ANOMALIES
# =====================================================================
with tab_mom:
    st.markdown("## 📈 Month-over-Month (MoM) Trend Anomalies")
    st.markdown("Detects historical time-series issues: Sudden Spikes, Flatlining Data, Category Shifts, and Multi-Indicator Copy-Paste errors.")
    
    # Run the dedicated trend engine
    mom_anomalies_df = run_trend_engine(financial_year, selected_district, facility_code)
    
    if not mom_anomalies_df.empty:
        st.error(f"🚨 Detected {len(mom_anomalies_df)} Trend Anomalies in {selected_district}")
        
        # Interactive Summary Table
        mom_abstract = mom_anomalies_df.groupby(['Anomaly Type', 'Pattern']).size().reset_index(name='Error Count').sort_values(by='Error Count', ascending=False)
        mom_abstract.insert(0, 'S.No', range(1, len(mom_abstract) + 1))
        
        st.markdown("### 📊 Trend Abstract")
        gridOptions_mom = build_grid_options(mom_abstract)
        AgGrid(mom_abstract, gridOptions=gridOptions_mom, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=True, height=300)
        
        st.markdown("### 🎯 Detailed Facility Trend Log")
        mom_details = mom_anomalies_df.copy()
        mom_details.insert(0, 'S.No', range(1, len(mom_details) + 1))
        
        gridOptions_mom_det = build_grid_options(mom_details)
        for col in gridOptions_mom_det['columnDefs']:
            if col['field'] == 'S.No': col['width'], col['pinned'], col['filter'] = 70, 'left', False
            elif col['field'] == 'Details': col['minWidth'], col['wrapText'], col['autoHeight'] = 300, True, True
            elif col['field'] not in ["Month", "District Name", "Facility Code"]: col['filter'] = False
            
        AgGrid(mom_details, gridOptions=gridOptions_mom_det, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=False, height=500)
        
        csv_mom = mom_details.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Trend Data", data=csv_mom, file_name="MoM_Trend_Anomalies.csv", mime="text/csv", type="primary")
        
    else:
        st.success("✅ No historical trend anomalies detected under the current filters.")

if is_admin:
    with tab3:
        st.subheader("🏢 Facility Wise Anomalies Table")
        
        if not master_anomalies_df.empty:
            # --- THE FIX: Drop Rule_ID before displaying ---
            df_facility = master_anomalies_df.drop(columns=['Rule_ID'], errors='ignore')
            
            df_facility.insert(0, 'S.No', range(1, len(df_facility) + 1))
            
            csv_data = df_facility.to_csv(index=False).encode('utf-8')
            col_spacer, col_dl = st.columns([4, 1])
            with col_dl:
                st.download_button("📥 Download Facility Data to CSV", data=csv_data, file_name="Facility_Wise_Anomalies.csv", mime="text/csv", type="primary", use_container_width=True)
                
            gridOptions_fac = build_grid_options(df_facility)
            
            for col in gridOptions_fac['columnDefs']:
                if col['field'] == 'S.No':
                    col['width'] = 80
                    col['pinned'] = 'left'
                    col['filter'] = False
                    
            AgGrid(df_facility, gridOptions=gridOptions_fac, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=False, height=500)
        else:
            st.success("✅ No anomalies found for the selected criteria.")

if is_admin:
    with tab4:
        st.subheader("🎯 Interactive Anomaly Rule Execution Viewer")
        
        active_cat_t4 = st.selectbox("📌 Select Anomaly Category:", [f"M{i}" for i in range(1, 18)], key="cat_tab4")
        rules_df = con.execute("SELECT Rule_ID, Rule_Description, Target_Format, Logic_LHS, Operator, Logic_RHS FROM rules_metadata_v3 WHERE Category_Code = ?", [active_cat_t4]).fetchdf()
        
        # --- FIX: THIS ENTIRE BLOCK MUST BE INDENTED UNDER 'with tab4:' ---
        if not rules_df.empty:
            rule_options = rules_df['Rule_ID'].tolist()
            
            col_label, col_radio = st.columns([1.5, 8.5])
            with col_label:
                st.markdown("<div style='margin-top: 14px; font-size: 16px; font-weight: bold;'>🎯 Select Rule No:</div>", unsafe_allow_html=True)
            with col_radio:
                selected_rule_id = st.radio("Select Rule", rule_options, horizontal=True, label_visibility="collapsed")
            
            rule_details = rules_df[rules_df['Rule_ID'] == selected_rule_id].iloc[0]
            st.markdown(f"<div class='chart-title' style='background-color:#ffeeba; border-color:#ffdf7e; color:#856404; margin-top: 5px; margin-bottom: 5px;'>{rule_details['Rule_Description']}</div>", unsafe_allow_html=True)
            
            import re
            lhs_raw = str(rule_details['Logic_LHS'])
            rhs_raw = str(rule_details['Logic_RHS'])
            op = str(rule_details['Operator'])
            t_format = str(rule_details['Target_Format'])
            
            all_metrics_raw = re.findall(r'\[(.*?)\]', lhs_raw) + re.findall(r'\[(.*?)\]', rhs_raw)
            metrics_in_rule = list(dict.fromkeys(all_metrics_raw))
            
            # --- REAL DATA PIPELINE FOR TAB 4 ---
            query = "SELECT * FROM hmis_master_data WHERE Financial_Year = ?"
            params = [financial_year]
            
            if selected_month != "All Months":
                query += " AND Month = ?"
                params.append(selected_month)
                
            if selected_district != "All Districts":
                query += ' AND "District Name" = ?'
                params.append(selected_district)
                
            if facility_code:
                query += ' AND "Facility Code" = ?'
                params.append(facility_code)
                
            try:
                df_rule_raw = con.execute(query, params).fetchdf()
            except:
                df_rule_raw = pd.DataFrame()
                
            if not df_rule_raw.empty:
                for m in metrics_in_rule:
                    if m in df_rule_raw.columns:
                        df_rule_raw[m] = pd.to_numeric(df_rule_raw[m], errors='coerce').fillna(0)
                
                if "All Formats" not in t_format:
                    formats = [f.strip() for f in t_format.split(',')]
                    df_rule_raw = df_rule_raw[df_rule_raw['Format Type'].isin(formats)]
                
                missing = [m for m in metrics_in_rule if m not in df_rule_raw.columns]
                
                if missing:
                    st.error(f"Missing columns in uploaded data: {missing}")
                    df_rule_output = pd.DataFrame()
                elif df_rule_raw.empty:
                    df_rule_output = pd.DataFrame()
                else:
                    eval_lhs, eval_rhs = lhs_raw, rhs_raw
                    for m in metrics_in_rule:
                        eval_lhs = eval_lhs.replace(f"[{m}]", f"`{m}`")
                        eval_rhs = eval_rhs.replace(f"[{m}]", f"`{m}`")
                    
                    eval_op = "==" if op == "=" else ("!=" if op == "<>" else op)
                    eval_str = f"({eval_lhs}) {eval_op} ({eval_rhs})"
                    
                    try:
                        mask = df_rule_raw.eval(eval_str)
                        df_rule_output = df_rule_raw[mask].copy()
                        
                        if not df_rule_output.empty:
                            df_rule_output['LHS Value'] = df_rule_output.eval(eval_lhs)
                            df_rule_output['RHS Value'] = df_rule_output.eval(eval_rhs)
                            df_rule_output['Difference (LHS - RHS)'] = df_rule_output['LHS Value'] - df_rule_output['RHS Value']
                            
                            base_cols = ["Month", "District Name", "Format Type", "Facility Code", "Facility Name"]
                            display_cols = [c for c in base_cols if c in df_rule_output.columns]
                            display_cols += metrics_in_rule + ['Difference (LHS - RHS)']
                            
                            df_rule_output = df_rule_output[display_cols]
                    except Exception as e:
                        st.error(f"Rule Evaluation Error: {e}")
                        df_rule_output = pd.DataFrame()
            else:
                df_rule_output = pd.DataFrame()

            # CONFIGURE THE GRID
            if not df_rule_output.empty:
                csv_data = df_rule_output.to_csv(index=False).encode('utf-8')
                col_spacer, col_dl = st.columns([4, 1])
                with col_dl:
                    st.download_button("📥 Download to CSV", data=csv_data, file_name="Detailed_Anomalies.csv", mime="text/csv", type="primary", use_container_width=True)
                
                df_rule_output.insert(0, 'S.No', range(1, len(df_rule_output) + 1))
                
                gridOptions_rule = build_grid_options(df_rule_output)
                
                for col in gridOptions_rule['columnDefs']:
                    if col['field'] == 'S.No':
                        col['width'] = 80
                        col['pinned'] = 'left'
                        col['filter'] = False
                    elif col['field'] not in ["Month", "District Name", "Format Type", "Facility Code", "Facility Name"]:
                        col['filter'] = False
                        
                AgGrid(df_rule_output, gridOptions=gridOptions_rule, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=False, height=500)
            else:
                st.success("✅ No anomalies found for this specific rule and filter combination.")

with tab5:
        st.subheader("📜 Dictionary of Active Anomaly Rules")
        st.markdown("All Single Month Rules stored in Master Database:")
        
        try:
            # --- FIX: Fetch ONLY the 7 required columns and ONLY Single Month rules ---
            rules_df = con.execute("""
                SELECT Category_Code, Rule_ID, Rule_Description, Target_Format, Logic_LHS, Operator, Logic_RHS 
                FROM rules_metadata_v3 
                WHERE Rule_Category = 'Single Month' OR Rule_Category IS NULL OR Rule_Type = 'Math'
            """).fetchdf()
            
            if not rules_df.empty:
                csv = rules_df.to_csv(index=False).encode('utf-8')
                col_spacer, col_dl = st.columns([4, 1])
                with col_dl:
                    st.download_button(label="📥 Download to CSV", data=csv, file_name="rules_dictionary.csv", mime="text/csv", type="primary", use_container_width=True)
                
                gridOptions_dict = build_grid_options(rules_df)
                
                for col in gridOptions_dict['columnDefs']:
                    if col['field'] in ['Category_Code', 'Rule_ID', 'Operator']:
                        col['width'] = 90
                        col['maxWidth'] = 100
                        col['filter'] = False
                        col['suppressSizeToFit'] = True
                    elif col['field'] == 'Target_Format':
                        col['width'] = 130
                        col['maxWidth'] = 150
                        col['filter'] = False
                        col['wrapText'] = True
                        col['autoHeight'] = True
                        col['suppressSizeToFit'] = True
                    elif col['field'] in ['Rule_Description', 'Logic_LHS', 'Logic_RHS']:
                        col['flex'] = 1  
                        col['minWidth'] = 200 
                        col['wrapText'] = True 
                        col['autoHeight'] = True 
                        col['filter'] = False
                
                # With only 7 columns, it is safe to turn auto-fit back on!
                AgGrid(rules_df, gridOptions=gridOptions_dict, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=True, height=600)
            else:
                st.info("No single-month rules found in the database.")
        except Exception as e:
            st.error(f"Error loading rules: {e}")

with tab6:
        st.subheader("📖 Monthly Service Delivery Indicators Mapping by Format Type")
        st.markdown("This tab displays the static list of all HMIS Monthly Service Delivery indicator names and their respective format types.")
        
        try:
            df_indicators = pd.read_excel("indicators_list.xlsx", header=1)
            
            # --- ADD DOWNLOAD BUTTON HERE ---
            csv_data = df_indicators.to_csv(index=False).encode('utf-8')
            col_spacer, col_dl = st.columns([4, 1])
            with col_dl:
                st.download_button("📥 Download to CSV", data=csv_data, file_name="Indicators_List.csv", mime="text/csv", type="primary", use_container_width=True)
            # --------------------------------
            
            # Clean the Excel data so the table doesn't crash
            df_indicators = df_indicators.dropna(how='all', axis=1) 
            df_indicators = df_indicators.fillna("") 
            df_indicators = df_indicators.astype(str) 
            
            if 'S.No' not in df_indicators.columns:
                df_indicators.insert(0, 'S.No', range(1, len(df_indicators) + 1))
                
            gridOptions_ind = build_grid_options(df_indicators)
            
            # --- ALIGNMENT & TEXT WRAPPING FIX ---
            for col in gridOptions_ind['columnDefs']:
                if col['field'] == 'S.No':
                    col['width'] = 70
                    col['maxWidth'] = 80
                    col['pinned'] = 'left'
                    col['suppressSizeToFit'] = True
                    col['filter'] = False
                elif col['field'] in ['Category', 'Data Item Code']:
                    col['width'] = 110
                    col['maxWidth'] = 130
                    col['suppressSizeToFit'] = True
                elif col['field'] == 'Data Item Name':
                    col['flex'] = 1           # Forces it to stretch and fill the middle
                    col['wrapText'] = True    # Wraps long text
                    col['autoHeight'] = True  # Adjusts row height
                    col['minWidth'] = 300
                else:
                    # For all the facility format type columns (SC, PHC, CHC, etc.)
                    col['width'] = 85
                    col['maxWidth'] = 100
                    col['suppressSizeToFit'] = True
                    col['filter'] = False
            # -------------------------------------
                    
            AgGrid(df_indicators, gridOptions=gridOptions_ind, theme='alpine', custom_css=shared_custom_css, fit_columns_on_grid_load=True, height=600)
            
        except FileNotFoundError:
            st.info("ℹ️ System is waiting for the file. Please place your Excel file in the same folder as 'app.py' and name it exactly **indicators_list.xlsx**.")
        except Exception as e:
            st.error(f"Error loading the Excel file: {e}")

if is_admin:
    with tabs[7]:
        st.subheader("🔒 State Admin & Database Access")
        
        admin_action = st.radio("Select Action", ["🧮 Add New Rule", "✏️ Edit/Delete Rule", "📤 Upload HMIS Data", "🔑 Change Password"], horizontal=True)
        st.divider()
        
        if admin_action == "📤 Upload HMIS Data":
            st.markdown("### 📤 Upload & Replace Raw Data")
            
            # Local dropdowns specifically for uploading
            col_fy, col_mo = st.columns(2)
            with col_fy:
                upload_fy = st.selectbox("Select Financial Year for Upload:", ["2026-27"])
            with col_mo:
                upload_months = [
                    "Apr-2026", "May-2026", "Jun-2026", "Jul-2026", "Aug-2026", "Sep-2026", 
                    "Oct-2026", "Nov-2026", "Dec-2026", "Jan-2027", "Feb-2027", "Mar-2027"
                ]
                # Changed to multi-select to support updating multiple months safely
                selected_upload_months = st.multiselect("Select Target Month(s) for Upload:", upload_months, default=["Apr-2026"])
            
            st.warning(f"⚠️ **Target Months:** You are uploading data for **{', '.join(selected_upload_months)} ({upload_fy})**. This action will **DELETE** any existing old data for these specific months and replace it with these new files.")
            
            # --- THE FIX: FORCE REBUILD CHECKBOX (Defaulted to False for safety) ---
            force_rebuild = st.checkbox("⚠️ Force Database Reset (Check this box ONLY to permanently wipe the database and start over)", value=False)
            
            uploaded_files = st.file_uploader("Upload raw monthly/annual HMIS data files (CSV/Excel)", type=["csv", "xlsx"], accept_multiple_files=True)
            
            if uploaded_files:
                if st.button("🚀 Process & Replace Database", type="primary"):
                    if not selected_upload_months:
                        st.error("❌ Please select at least one Target Month from the dropdown.")
                    else:
                        with st.spinner("Processing massive dataset... please wait."):
                            success_count = 0
                            
                            for file in uploaded_files:
                                try:
                                    # Memory-safe file reading via local hard drive buffer
                                    temp_file_path = f"temp_{file.name}"
                                    with open(temp_file_path, "wb") as f:
                                        f.write(file.getbuffer())
                                    
                                    if temp_file_path.endswith('.csv'):
                                        df_raw = pd.read_csv(temp_file_path)
                                    else:
                                        df_raw = pd.read_excel(temp_file_path)
                                        
                                    import os
                                    if os.path.exists(temp_file_path):
                                        os.remove(temp_file_path)
                                    
                                    # --- DATA SANITIZER FOR HEADERS ---
                                    import re
                                    def clean_header(col_name):
                                        c = str(col_name).replace('\xa0', ' ') # Destroy hidden ghost spaces
                                        c = c.strip() # Remove invisible trailing/leading spaces
                                        c = re.sub(r'\s+', ' ', c) # Fix accidental double-spaces
                                        return c
                                    
                                    df_raw.columns = [clean_header(c) for c in df_raw.columns]
                                    # -------------------------------------------
                                    
                                    # 2. Add required metadata variables
                                    df_raw['Financial_Year'] = upload_fy
                                    
                                    # Assign month logic: if single month selected, apply it; if multiple, expect file to have its own Month column
                                    if len(selected_upload_months) == 1:
                                        df_raw['Month'] = selected_upload_months[0]
                                    elif 'Month' not in df_raw.columns:
                                        st.error(f"❌ Error: {file.name} does not contain a 'Month' column, but you selected multiple target months. Please upload files individually or ensure a Month column is present.")
                                        continue
                                    
                                    # 3. Convert Facility Code to string
                                    if 'Facility Code' in df_raw.columns:
                                        df_raw['Facility Code'] = df_raw['Facility Code'].astype(str)
                                    
                                    # 4. Smart Database Merge Logic
                                    try:
                                        # If the user explicitly checked the full reset box on the first file
                                        if force_rebuild and success_count == 0:
                                            con.execute("DROP TABLE IF EXISTS hmis_master_data")
                                            
                                        current_cols = con.execute("DESCRIBE hmis_master_data").fetchdf()
                                        
                                        # Blow up old mock table if it exists (fewer than 50 columns)
                                        if len(current_cols) < 50:
                                            con.execute("DROP TABLE IF EXISTS hmis_master_data")
                                            con.execute("CREATE TABLE hmis_master_data AS SELECT * FROM df_raw")
                                        else:
                                            # If this is the first file in the loop, safely wipe ONLY the targeted months
                                            if success_count == 0 and not force_rebuild:
                                                for target_mo in selected_upload_months:
                                                    con.execute("DELETE FROM hmis_master_data WHERE Financial_Year = ? AND Month = ?", [upload_fy, target_mo])
                                            
                                            db_columns = con.execute("SELECT * FROM hmis_master_data LIMIT 0").fetchdf().columns
                                            for col in db_columns:
                                                if col not in df_raw.columns:
                                                    df_raw[col] = None 
                                            df_raw = df_raw[db_columns]
                                            con.execute("INSERT INTO hmis_master_data SELECT * FROM df_raw")
                                            
                                    except Exception as e:
                                        # If table completely doesn't exist, create it cleanly!
                                        con.execute("CREATE TABLE hmis_master_data AS SELECT * FROM df_raw")
                                        
                                    success_count += 1
                                except Exception as e:
                                    st.error(f"❌ Error processing {file.name}: {e}")
                        
                            if success_count > 0:
                                st.success(f"✅ Successfully processed {success_count} new file(s) into the Master Database! (Columns matched: {len(df_raw.columns)})")
                                st.balloons()
                                st.cache_data.clear()

        elif admin_action == "🧮 Add New Rule":
            st.markdown("### 🛠️ Advanced Formula Engine")
            
            # Show success messages that persist after the screen clears
            if 'admin_success' in st.session_state:
                st.success(st.session_state.admin_success)
                del st.session_state.admin_success

            # --- FORM CLEARING LOGIC ---
            if st.session_state.get("clear_math_form"):
                st.session_state["new_desc"] = ""
                st.session_state["lhs_input"] = ""
                st.session_state["rhs_input"] = ""
                st.session_state["clear_math_form"] = False
                
            if st.session_state.get("clear_trend_form"):
                st.session_state["new_desc"] = ""
                st.session_state["trend_val"] = ""
                st.session_state["clear_trend_form"] = False

            # --- CALLBACK FUNCTIONS FOR ADDING METRICS ---
            def add_metric_lhs():
                m = st.session_state.get("helper_add")
                if m and m != "-- Select a metric --":
                    curr = st.session_state.get("lhs_input", "")
                    st.session_state.lhs_input = (curr if curr else "") + f"[{m}] "

            def add_metric_rhs():
                m = st.session_state.get("helper_add")
                if m and m != "-- Select a metric --":
                    curr = st.session_state.get("rhs_input", "")
                    st.session_state.rhs_input = (curr if curr else "") + f"[{m}] "

            # --- CATEGORY & ID AUTO-GENERATOR ---
            col_cat, col_id = st.columns([1, 1])
            with col_cat:
                new_rule_cat = st.selectbox("Assign to Category", [f"M{i}" for i in range(1, 18)], key="new_cat")
            
            try:
                cat_rules = con.execute("SELECT Rule_ID FROM rules_metadata_v3 WHERE Category_Code = ?", [new_rule_cat]).fetchdf()
                if not cat_rules.empty:
                    import re
                    max_num = 0
                    for r_id in cat_rules['Rule_ID']:
                        match = re.search(r'\d+$', str(r_id)) 
                        if match:
                            num = int(match.group())
                            max_num = max(max_num, num)
                    next_num = max_num + 1
                else:
                    next_num = 1
            except:
                next_num = 1
                
            # --- THE FIX: Reverting back to just the pure number ---
            suggested_id = str(next_num)
            
            with col_id:
                new_rule_id = st.text_input("Rule ID (Number)", value=suggested_id)

            # --- FORMATS & DYNAMIC DIMENSIONS ---
            format_options = ["All Formats", "SC Format", "PHC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College"]
            target_format_list = st.multiselect("Applies to Format Type(s)", format_options, default=["All Formats"], key="new_fmt")
            target_format = ", ".join(target_format_list) 
            
            has_phc = "PHC Format" in target_format_list or "All Formats" in target_format_list
            has_non_phc = any(f in target_format_list for f in ["SC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College", "All Formats"])
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                if has_phc:
                    phc_area_scope = st.selectbox("🏡 PHC Area Scope (Applies only to PHC)", ["All", "Rural", "Urban"])
                else:
                    phc_area_scope = "All"
                    st.caption("ℹ️ Area Scope inactive (PHC Format not selected).")
            with col_d2:
                if has_non_phc:
                    non_phc_ownership = st.selectbox("🏥 Ownership (Applies only to Non-PHC)", ["All", "Public", "Private"])
                else:
                    non_phc_ownership = "All"
                    st.caption("ℹ️ Ownership inactive (Only PHC Format selected).")

            if 'new_desc' not in st.session_state: st.session_state.new_desc = ""
            new_rule_desc = st.text_input("Rule Description", key="new_desc", placeholder="Briefly describe the anomaly...")
            
            rule_type = st.radio("Rule Type", ["Single Month Validation", "Month-over-Month Trend Validation"], horizontal=True, key="new_type")
            
            # =====================================================================
            # LOGIC BUILDER: SINGLE MONTH VALIDATION
            # =====================================================================
            if rule_type == "Single Month Validation":
                st.info("💡 **Click the box below and start typing to search.** Then click to add it to your formula.")
                helper_metric = st.selectbox("🔍 Search & Select Metric Name (Type to search)", ["-- Select a metric --"] + ALL_METRICS_LIST, key="helper_add")
                
                if 'lhs_input' not in st.session_state: st.session_state.lhs_input = ""
                if 'rhs_input' not in st.session_state: st.session_state.rhs_input = ""
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1: st.button("➕ Add to LHS Box", key="btn_add_lhs", on_click=add_metric_lhs, use_container_width=True)
                with col_btn2: st.button("➕ Add to RHS Box", key="btn_add_rhs", on_click=add_metric_rhs, use_container_width=True)
                    
                col_lhs, col_op, col_rhs = st.columns([4, 1, 4])
                with col_lhs: lhs_expr = st.text_area("Left Hand Side (LHS)", key="lhs_input")
                with col_op: operator = st.selectbox("Operator", [">", "<", ">=", "<=", "==", "!=", "<>"])
                with col_rhs: rhs_expr = st.text_area("Right Hand Side (RHS)", key="rhs_input")
                    
                if st.button("💾 Save Mathematical Rule", type="primary"):
                    check_dup = con.execute("SELECT COUNT(*) FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [new_rule_cat, new_rule_id]).fetchone()[0]
                    if not new_rule_id or not new_rule_desc:
                        st.markdown("<p style='color:red; font-weight:bold; font-size:16px;'>❌ Rule ID and Rule Description cannot be empty.</p>", unsafe_allow_html=True)
                    elif check_dup > 0:
                        st.markdown(f"<p style='color:red; font-weight:bold; font-size:16px;'>❌ ERROR: Rule '{new_rule_id}' exists!</p>", unsafe_allow_html=True)
                    else:
                        try:
                            # Inserting all 15 columns safely
                            con.execute(
                                "INSERT INTO rules_metadata_v3 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                [new_rule_cat, new_rule_id, new_rule_desc, target_format, 'Math', lhs_expr, operator, rhs_expr, True,
                                 "Single Month", "None", phc_area_scope, non_phc_ownership, 1, 0.0]
                            )
                            st.session_state.clear_math_form = True
                            st.session_state.admin_success = f"✅ Rule {new_rule_id} saved successfully! Form cleared."
                            st.cache_data.clear()     
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")
                            
            # =====================================================================
            # LOGIC BUILDER: MONTH-OVER-MONTH TREND VALIDATION
            # =====================================================================
            else:
                st.markdown("#### 📉 Trend Pattern Engine")
                trend_pattern = st.selectbox(
                    "Select Trend Pattern to Monitor",
                    [
                        "⚡ Sudden Spike / Extreme Outlier",
                        "🔄 Repeated Constant Values / Flatline",
                        "⚠️ Category Shift / Zero-to-Max Anomaly",
                        "📋 Multi-Indicator Copy-Paste"
                    ]
                )
                
                if "Sudden Spike" in trend_pattern:
                    st.info("💡 Search and select the metric to track for spikes.")
                    target_raw = st.selectbox("🔍 Target Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="spike_metric")
                    target_metric = f"[{target_raw}]" if target_raw != "-- Select a metric --" else ""
                    
                    c_w, c_t = st.columns(2)
                    with c_w: trend_window = st.slider("Lookback Baseline Window (Months)", 2, 12, 6)
                    with c_t: trend_threshold = st.number_input("Spike Multiplier (x historical avg)", 1.5, 20.0, 3.0, 0.5)
                    lhs_expr, operator, rhs_expr = target_metric, ">", f"Moving_Avg({trend_window}M) * {trend_threshold}"
                    
                elif "Repeated Constant" in trend_pattern:
                    st.info("💡 Search and select the metric to track for flatlining data.")
                    target_raw = st.selectbox("🔍 Target Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="flat_metric")
                    target_metric = f"[{target_raw}]" if target_raw != "-- Select a metric --" else ""
                    
                    trend_window = st.slider("Consecutive Months Required with Identical Value", 2, 12, 4)
                    trend_threshold = 0.0
                    lhs_expr, operator, rhs_expr = target_metric, "==", f"LAG({trend_window}M Continuous Match)"
                    
                elif "Category Shift" in trend_pattern:
                    st.info("💡 Select the sub-indicator and its parent total to check for sudden ratio shifts.")
                    c_s, c_p = st.columns(2)
                    with c_s: 
                        sub_raw = st.selectbox("🔍 Sub-Indicator (Under-reported)", ["-- Select a metric --"] + ALL_METRICS_LIST, key="cat_sub")
                        sub_ind = f"[{sub_raw}]" if sub_raw != "-- Select a metric --" else ""
                    with c_p: 
                        tot_raw = st.selectbox("🔍 Total / Parent Indicator", ["-- Select a metric --"] + ALL_METRICS_LIST, key="cat_tot")
                        tot_ind = f"[{tot_raw}]" if tot_raw != "-- Select a metric --" else ""
                        
                    trend_window = st.slider("Historical Lookback Zero Window (Months)", 3, 12, 6)
                    trend_threshold = st.slider("Current Month Minimum Share (%)", 50, 100, 90)
                    lhs_expr, operator, rhs_expr = f"({sub_ind} / {tot_ind}) * 100", ">=", f"{trend_threshold}%"
                    
                elif "Copy-Paste" in trend_pattern:
                    st.info("💡 Type or paste the indicators that should NOT match, separated by commas.")
                    lhs_expr = st.text_area("Indicators Expected to Differ", "[1.1.2], [1.2.4], [1.2.5], [1.2.7]")
                    trend_window, trend_threshold = 1, 0.0
                    operator, rhs_expr = "==", "All Values Identical"
                
                if st.button("💾 Save Trend Rule", type="primary"):
                    check_dup = con.execute("SELECT COUNT(*) FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [new_rule_cat, new_rule_id]).fetchone()[0]
                    
                    # Prevent saving if a dropdown is left empty
                    if not new_rule_id or not new_rule_desc or not lhs_expr or "-- Select" in lhs_expr:
                        st.markdown("<p style='color:red; font-weight:bold; font-size:16px;'>❌ Rule ID, Description, and valid Indicators are required.</p>", unsafe_allow_html=True)
                    elif check_dup > 0:
                        st.markdown(f"<p style='color:red; font-weight:bold; font-size:16px;'>❌ ERROR: Rule '{new_rule_id}' exists!</p>", unsafe_allow_html=True)
                    else:
                        try:
                            con.execute(
                                "INSERT INTO rules_metadata_v3 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                [new_rule_cat, new_rule_id, new_rule_desc, target_format, 'Trend', lhs_expr, operator, rhs_expr, True,
                                 "MoM Trend", trend_pattern, phc_area_scope, non_phc_ownership, int(trend_window), float(trend_threshold)]
                            )
                            st.session_state.clear_trend_form = True
                            st.session_state.admin_success = f"✅ Trend Rule {new_rule_id} saved successfully! Form cleared."
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")

        elif admin_action == "✏️ Edit/Delete Rule":
            st.markdown("### ✏️ Edit or Delete Existing Rules")
            
            if 'admin_success' in st.session_state:
                st.success(st.session_state.admin_success)
                del st.session_state.admin_success
                
            def edit_metric_lhs():
                m = st.session_state.get("helper_edit")
                if m and m != "-- Select a metric --":
                    curr = st.session_state.get("edit_lhs_input", "")
                    st.session_state.edit_lhs_input = (curr if curr else "") + f"[{m}] "

            def edit_metric_rhs():
                m = st.session_state.get("helper_edit")
                if m and m != "-- Select a metric --":
                    curr = st.session_state.get("edit_rhs_input", "")
                    st.session_state.edit_rhs_input = (curr if curr else "") + f"[{m}] "
            
            edit_cat = st.selectbox("📌 Select Category to Edit/Delete From", [f"M{i}" for i in range(1, 18)], key="edit_cat_select")
            
            try:
                all_rules_df = con.execute("SELECT Rule_ID FROM rules_metadata_v3 WHERE Category_Code = ?", [edit_cat]).fetchdf()
                all_rules = ["-- Select a Rule --"] + all_rules_df['Rule_ID'].astype(str).tolist()
            except:
                all_rules = ["-- Select a Rule --"]
                
            if len(all_rules) == 1:
                st.info(f"No rules exist in category {edit_cat} yet.")
            else:
                rule_to_edit = st.selectbox("📌 Select Rule to Edit/Delete", all_rules)
                
                if rule_to_edit != "-- Select a Rule --":
                    rule_details = con.execute("SELECT * FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [edit_cat, rule_to_edit]).fetchdf().iloc[0]
                    
                    edit_tracking_key = f"{edit_cat}_{rule_to_edit}"
                    if 'current_edit_rule' not in st.session_state or st.session_state.current_edit_rule != edit_tracking_key:
                        st.session_state.current_edit_rule = edit_tracking_key
                        st.session_state.edit_desc = str(rule_details['Rule_Description'])
                        st.session_state.edit_lhs_input = str(rule_details['Logic_LHS'])
                        st.session_state.edit_rhs_input = str(rule_details['Logic_RHS'])
                    
                    st.write(f"Modifying: Category **{edit_cat}** - Rule **{rule_to_edit}**")
                    
                    edit_desc = st.text_input("Rule Description", key="edit_desc")
                    
                    # FORMAT & DIMENSION EDITING
                    format_options = ["All Formats", "SC Format", "PHC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College"]
                    current_fmt = str(rule_details['Target_Format'])
                    try:
                        pre_selected_formats = [f.strip() for f in current_fmt.split(',')]
                    except:
                        pre_selected_formats = ["All Formats"]
                        
                    edit_fmt = st.multiselect("Applies to Format Type(s)", format_options, default=pre_selected_formats, key="edit_fmt")
                    new_formats_string = ", ".join(edit_fmt)
                    
                    has_phc = "PHC Format" in edit_fmt or "All Formats" in edit_fmt
                    has_non_phc = any(f in edit_fmt for f in ["SC Format", "CHC Format", "SDH Format", "DH Format", "Ayush Format", "Medical College", "All Formats"])
                    
                    curr_phc = str(rule_details.get('PHC_Area_Scope', 'All'))
                    curr_non = str(rule_details.get('Non_PHC_Ownership', 'All'))
                    
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        if has_phc:
                            idx_phc = ["All", "Rural", "Urban"].index(curr_phc) if curr_phc in ["All", "Rural", "Urban"] else 0
                            edit_phc = st.selectbox("🏡 PHC Area Scope", ["All", "Rural", "Urban"], index=idx_phc)
                        else:
                            edit_phc = "All"
                    with col_d2:
                        if has_non_phc:
                            idx_non = ["All", "Public", "Private"].index(curr_non) if curr_non in ["All", "Public", "Private"] else 0
                            edit_non_phc = st.selectbox("🏥 Ownership", ["All", "Public", "Private"], index=idx_non)
                        else:
                            edit_non_phc = "All"

                    st.info("💡 **Click the box below and start typing to search.** Then click to add it to your formula.")
                    helper_metric_edit = st.selectbox("🔍 Search & Select Metric Name (Type to search)", ["-- Select a metric --"] + ALL_METRICS_LIST, key="helper_edit")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1: st.button("➕ Add to LHS Box", key="btn_add_lhs_edit", on_click=edit_metric_lhs, use_container_width=True)
                    with col_btn2: st.button("➕ Add to RHS Box", key="btn_add_rhs_edit", on_click=edit_metric_rhs, use_container_width=True)
                    
                    col_lhs, col_op, col_rhs = st.columns([4, 1, 4])
                    with col_lhs: edit_lhs = st.text_area("Left Hand Side (LHS)", key="edit_lhs_input")
                    with col_op:
                        ops = [">", "<", ">=", "<=", "==", "!=", "<>"]
                        current_op = str(rule_details['Operator'])
                        op_idx = ops.index(current_op) if current_op in ops else 0
                        edit_op = st.selectbox("Operator", ops, index=op_idx, key="edit_op")
                    with col_rhs: edit_rhs = st.text_area("Right Hand Side (RHS)", key="edit_rhs_input")
                    
                    st.write("")
                    col_save, col_del = st.columns(2)
                    
                    if col_save.button("💾 Save Changes", type="primary", use_container_width=True):
                        try:
                            # Safely update using BOTH Category Code and Rule ID + new dimensions
                            con.execute("""
                                UPDATE rules_metadata_v3 
                                SET Rule_Description = ?, Target_Format = ?, Logic_LHS = ?, Operator = ?, Logic_RHS = ?, PHC_Area_Scope = ?, Non_PHC_Ownership = ?
                                WHERE Category_Code = ? AND Rule_ID = ?
                            """, [edit_desc, new_formats_string, edit_lhs, edit_op, edit_rhs, edit_phc, edit_non_phc, edit_cat, rule_to_edit])
                            
                            for key in ['edit_desc', 'edit_lhs_input', 'edit_rhs_input', 'current_edit_rule']:
                                if key in st.session_state: del st.session_state[key]
                                
                            st.session_state.admin_success = f"✅ Rule {rule_to_edit} in {edit_cat} updated successfully!"
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating rule: {e}")
                            
                    if col_del.button("🗑️ Permanently Delete Rule", use_container_width=True):
                        try:
                            con.execute("DELETE FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?", [edit_cat, rule_to_edit])
                            
                            for key in ['edit_desc', 'edit_lhs_input', 'edit_rhs_input', 'current_edit_rule']:
                                if key in st.session_state: del st.session_state[key]
                                
                            st.session_state.admin_success = f"🗑️ Rule {rule_to_edit} in {edit_cat} deleted permanently!"
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting rule: {e}")

        elif admin_action == "🔑 Change Password":
            st.markdown("### 🔑 Change Admin Password")
            
            with st.form("change_password_form"):
                old_pwd = st.text_input("Current Password", type="password")
                new_pwd = st.text_input("New Password", type="password")
                confirm_pwd = st.text_input("Confirm New Password", type="password")
                
                st.write("")
                submit_pwd = st.form_submit_button("💾 Update Password", type="primary")
                
                if submit_pwd:
                    if old_pwd != current_db_password:
                        st.error("❌ Current password is incorrect.")
                    elif new_pwd != confirm_pwd:
                        st.error("❌ New passwords do not match.")
                    elif len(new_pwd) < 5:
                        st.error("❌ Password must be at least 5 characters long.")
                    else:
                        try:
                            con.execute("UPDATE admin_settings SET setting_value = ? WHERE setting_name = 'admin_password'", [new_pwd])
                            st.success("✅ Password updated successfully! Please re-enter your new password in the sidebar to keep Admin access.")
                        except Exception as e:
                            st.error(f"Database error: {e}")
