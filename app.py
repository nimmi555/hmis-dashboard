"""HMIS Data Validation Dashboard - Andhra Pradesh.

Streamlit + DuckDB. Rule-driven anomaly engine (single-month + month-over-month
trend patterns), interactive drill-down, password-gated admin console.
"""

import re
import textwrap

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="HMIS Anomalies", layout="wide", initial_sidebar_state="expanded")

# =====================================================================
# THEME (Looker Studio style)
# =====================================================================
st.markdown("""
    <style>
        /* ---------- LAYOUT ---------- */
        .block-container { padding: 3rem 2rem 1rem !important; max-width: 100% !important; }
        .stAppDeployButton { display: none !important; }
        div.stMarkdown { margin-bottom: -15px !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.5rem !important; }

        /* ---------- COLORS ---------- */
        .stApp { background-color: #fdfbed; }
        [data-testid="stTabs"] {
            background-color: #ffffff; padding: 20px; border-radius: 10px;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
        }

        /* ---------- TABS ---------- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px; background-color: #ffffff; padding: 10px 15px; border-radius: 12px;
            box-shadow: 0px 2px 8px rgba(0,0,0,0.06); border-bottom: 4px solid #4285F4;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #f1f3f4 !important; border-radius: 8px !important;
            padding: 10px 20px !important; color: #3c4043 !important; font-size: 15px !important;
            font-weight: 800 !important; border: 1px solid #dadce0 !important;
            transition: all 0.2s ease-in-out;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #e8f0fe !important; color: #1a73e8 !important; border-color: #8ab4f8 !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1a73e8 !important; color: white !important;
            border: 1px solid #1a73e8 !important; box-shadow: 0px 4px 10px rgba(26, 115, 232, 0.3);
        }
        .stTabs [data-baseweb="tab-highlight"] { display: none; }

        /* ---------- SIDEBAR ---------- */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa; border-right: 1px solid #e0e0e0; padding-top: 1rem;
        }
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] label {
            color: #202124 !important; font-weight: 700 !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] input {
            background-color: #ffffff !important; border-radius: 8px !important;
            border: 1px solid #ced4da !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"] {
            background-color: #1a73e8 !important; color: white !important;
            border-radius: 8px !important; font-weight: bold !important; border: none !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover { background-color: #1557b0 !important; }

        /* ---------- HEADERS & TILES ---------- */
        .ds-yellow-header {
            background-color: #e5ff4c; padding: 10px; border-radius: 20px; text-align: center;
            border: 1px solid #000; color: #0000bb; font-weight: bold; font-size: 24px; margin-bottom: 10px;
        }
        .kpi-tile {
            background-color: #ffffff; border-radius: 10px; padding: 20px; text-align: center;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.1); border-top: 5px solid #4285F4;
        }
        .kpi-title { font-size: 20px; font-weight: 800; color: #333; margin-bottom: 10px; }
        .kpi-value { font-size: 38px; font-weight: bold; color: #000; }
        .chart-title {
            background-color: #cce5ff; padding: 10px; border-radius: 8px; text-align: center;
            font-size: 18px; font-weight: 800; color: #004085; margin-bottom: 15px;
            border: 1px solid #b8daff;
        }

        /* ---------- BUTTONS ---------- */
        div[data-testid="stDownloadButton"] > button {
            background-color: #198754 !important; color: white !important;
            border: none !important; font-weight: bold !important;
        }
        div[data-testid="stDownloadButton"] > button:hover { background-color: #146c43 !important; }
        [data-testid="stElementToolbarButton"] svg {
            width: 1.8rem !important; height: 1.8rem !important; color: #4285F4 !important;
        }

        /* ---------- CLICK-ME INSTRUCTION ---------- */
        @keyframes sparkle-animation {
            0%   { color: #D32F2F; text-shadow: 0 0 4px rgba(211,47,47,0.6); transform: scale(1); }
            50%  { color: #00B0FF; text-shadow: 0 0 10px #00B0FF, 0 0 20px #40C4FF; transform: scale(1.02); }
            100% { color: #D32F2F; text-shadow: 0 0 4px rgba(211,47,47,0.6); transform: scale(1); }
        }
        .animated-instruction {
            font-size: 24px; font-weight: 900; margin-left: 15px;
            animation: sparkle-animation 1.5s ease-in-out infinite;
        }
        .header-wrapper {
            font-size: 26px; font-weight: bold; margin-bottom: 20px; display: flex;
            align-items: center; border-bottom: 2px solid #eeeeee; padding-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# METRIC DICTIONARY
# =====================================================================
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
4.5.1.a :: Number of Newborns identified with visible birth defects (including Neural tube defect, Down's Syndrome, Cleft Lip & Palate, Club foot and Developmental dysplasia of the hip)
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
14.1.1.h :: Number of elderly support groups-'Sanjeevini' created during the month
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
ALL_METRICS_LIST = [m.strip() for m in RAW_METRICS.strip().split("\n") if m.strip()]

# =====================================================================
# CONSTANTS
# =====================================================================
BASE_COLS = ["Month", "District Name", "Format Type", "Facility Code", "Facility Name"]
CATEGORIES = [f"M{i}" for i in range(1, 18)]
FORMAT_OPTIONS = ["All Formats", "SC Format", "PHC Format", "CHC Format", "SDH Format",
                  "DH Format", "Ayush Format", "Medical College"]
NON_PHC_FORMATS = ["SC Format", "CHC Format", "SDH Format", "DH Format",
                   "Ayush Format", "Medical College", "All Formats"]
OPERATORS = [">", "<", ">=", "<=", "==", "!=", "<>"]
PICK = "-- Select a metric --"
PRIVATE_PATTERN = "Private|Pvt|Trust|NGO"

GRID_CSS = {
    ".ag-header-cell-text": {"font-size": "14px", "font-weight": "900", "color": "#004085"},
    ".ag-header-cell-label": {"justify-content": "center"},
    ".ag-header-cell": {"border-right": "1px solid #dee2e6"},
}
CELL_STYLE = {
    "textAlign": "center", "backgroundColor": "#ffffff", "color": "#000000",
    "fontSize": "14px", "fontWeight": "bold",
    "borderRight": "1px solid #dee2e6", "borderBottom": "1px solid #dee2e6",
}
WRAP_COL = {"flex": 1, "wrapText": True, "autoHeight": True}


# =====================================================================
# DATABASE
# =====================================================================
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

    # Auto-migration: dimensions & MoM trend columns
    try:
        existing = [r[1] for r in con.execute("PRAGMA table_info('rules_metadata_v3')").fetchall()]
        for col, definition in {
            "Rule_Category": "VARCHAR DEFAULT 'Single Month'",
            "Trend_Pattern": "VARCHAR DEFAULT 'None'",
            "PHC_Area_Scope": "VARCHAR DEFAULT 'All'",
            "Non_PHC_Ownership": "VARCHAR DEFAULT 'All'",
            "Trend_Window_Months": "INTEGER DEFAULT 3",
            "Trend_Threshold": "FLOAT DEFAULT 3.0",
        }.items():
            if col not in existing:
                con.execute(f"ALTER TABLE rules_metadata_v3 ADD COLUMN {col} {definition}")
    except Exception:
        pass

    con.execute("CREATE TABLE IF NOT EXISTS admin_settings (setting_name VARCHAR, setting_value VARCHAR)")
    if not con.execute("SELECT * FROM admin_settings WHERE setting_name = 'admin_password'").fetchone():
        con.execute("INSERT INTO admin_settings VALUES ('admin_password', 'admin123')")
    return con


con = init_db()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_hmis_data(sel_fy):
    """Fetch a whole FY once and share it across all sessions in RAM."""
    try:
        return con.execute("SELECT * FROM hmis_master_data WHERE Financial_Year = ?", [sel_fy]).fetchdf()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_rules():
    try:
        return con.execute("SELECT * FROM rules_metadata_v3").fetchdf()
    except Exception:
        return pd.DataFrame()


# =====================================================================
# SHARED LOGIC HELPERS
# =====================================================================
def apply_global_filters(df, month=None, district=None, fac_code=None):
    """Sidebar filters. Pass month=None to keep full history (trend engine)."""
    if month and month != "All Months":
        df = df[df["Month"] == month]
    if district and district != "All Districts":
        df = df[df["District Name"] == district]
    if fac_code:
        df = df[df["Facility Code"].astype(str) == str(fac_code)]
    return df


def apply_rule_scope(df, rule):
    """Restrict rows to the formats / area / ownership a rule targets."""
    fmt = str(rule.get("Target_Format", "All Formats"))
    if "All Formats" not in fmt:
        df = df[df["Format Type"].isin([f.strip() for f in fmt.split(",")])]

    phc_scope = str(rule.get("PHC_Area_Scope", "All"))
    if phc_scope in ("Rural", "Urban") and "Rural/Urban" in df.columns:
        is_phc = df["Format Type"] == "PHC Format"
        match = df["Rural/Urban"].astype(str).str.strip().str.upper() == phc_scope.upper()
        df = df[(~is_phc) | (is_phc & match)]

    ownership = str(rule.get("Non_PHC_Ownership", "All"))
    if ownership in ("Public", "Private"):
        non_phc = df["Format Type"] != "PHC Format"
        if "Ownership" in df.columns:
            match = df["Ownership"].astype(str).str.strip().str.upper() == ownership.upper()
        elif "Facility Name" in df.columns:
            is_pvt = df["Facility Name"].str.contains(PRIVATE_PATTERN, case=False, na=False)
            match = is_pvt if ownership == "Private" else ~is_pvt
        else:
            return df
        df = df[(~non_phc) | (non_phc & match)]
    return df


def evaluate_rule(rule, df):
    """Run one single-month rule. Returns (failing rows, metrics used, missing columns)."""
    lhs, rhs, op = str(rule["Logic_LHS"]), str(rule["Logic_RHS"]), str(rule["Operator"])
    metrics = list(dict.fromkeys(re.findall(r"\[(.*?)\]", lhs) + re.findall(r"\[(.*?)\]", rhs)))

    df = apply_rule_scope(df, rule)
    missing = [m for m in metrics if m not in df.columns]
    if df.empty or missing:
        return pd.DataFrame(), metrics, missing

    df = df.copy()
    for m in metrics:
        df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0)
        lhs, rhs = lhs.replace(f"[{m}]", f"`{m}`"), rhs.replace(f"[{m}]", f"`{m}`")

    op = {"=": "==", "<>": "!="}.get(op, op)
    hits = df[df.eval(f"({lhs}) {op} ({rhs})")].copy()
    if not hits.empty:
        hits["LHS Value"] = hits.eval(lhs)
        hits["RHS Value"] = hits.eval(rhs)
        hits["Difference (LHS - RHS)"] = hits["LHS Value"] - hits["RHS Value"]
    return hits, metrics, missing


def detail_columns(df, metrics):
    return [c for c in BASE_COLS if c in df.columns] + metrics + ["Difference (LHS - RHS)"]


# =====================================================================
# UI HELPERS
# =====================================================================
def build_grid_options(df, col_cfg=(), row_selection=None):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        wrapHeaderText=True, autoHeaderHeight=True, resizable=True, wrapText=True,
        autoHeight=True, sortable=True, filter=False, suppressMenu=True, cellStyle=CELL_STYLE,
    )
    opts = gb.build()
    opts["suppressMenuHide"] = True
    if row_selection:
        opts["rowSelection"] = row_selection
    for col in opts["columnDefs"]:
        for match, props in col_cfg:
            hit = match(col["field"]) if callable(match) else col["field"] == match
            if hit:
                col.update(props)
    return opts


def show_grid(df, col_cfg=(), height=500, fit=False, key=None, css=None, row_selection=None, **kwargs):
    return AgGrid(df, gridOptions=build_grid_options(df, col_cfg, row_selection), theme="alpine",
                  custom_css=css or GRID_CSS, fit_columns_on_grid_load=fit,
                  height=height, key=key, **kwargs)


def download_csv(df, filename, key=None, label="📥 Download to CSV", ratio=(4, 1)):
    with st.columns(list(ratio))[-1]:
        st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename,
                           mime="text/csv", type="primary", use_container_width=True, key=key)


def kpi_tile(title, value, color, note, note_color="#6c757d", bold=False):
    weight = "font-weight:bold;" if bold else ""
    st.markdown(
        f'<div class="kpi-tile" style="border-top: 5px solid {color};">'
        f'<div class="kpi-title">{title}</div><div class="kpi-value">{value}</div>'
        f'<div style="color:{note_color}; font-size:14px; {weight}">{note}</div></div>',
        unsafe_allow_html=True)


def total_bar(label, value):
    st.markdown(
        f'<div style="background-color:#ff9800; color:#000; font-weight:900; font-size:16px;'
        f' padding:12px; border-radius:5px; display:flex; justify-content:space-between;'
        f' margin-top:10px;"><span>{label}</span><span>{value:,}</span></div>',
        unsafe_allow_html=True)


def red(msg):
    st.markdown(f"<p style='color:red; font-weight:bold; font-size:16px;'>{msg}</p>", unsafe_allow_html=True)


# =====================================================================
# SIDEBAR: GLOBAL FILTERS
# =====================================================================
st.sidebar.header("🔍 Global Filters")
financial_year = st.sidebar.selectbox("Financial Year", ["2026-27"])

try:
    db_months = con.execute(
        "SELECT DISTINCT Month FROM hmis_master_data WHERE Month IS NOT NULL").fetchdf()["Month"].tolist()
    db_districts = con.execute(
        'SELECT DISTINCT "District Name" FROM hmis_master_data WHERE "District Name" IS NOT NULL'
    ).fetchdf()["District Name"].tolist()
except Exception:
    db_months, db_districts = [], []

month_list = ["All Months"] + db_months if db_months else \
    ["All Months", "Apr-2026", "May-2026", "Jun-2026", "Jul-2026", "Aug-2026", "Sep-2026"]
district_list = ["All Districts"] + sorted(db_districts) if db_districts else \
    ["All Districts", "Anakapalli", "Eluru", "Kakinada", "Nandyal"]

selected_month = st.sidebar.selectbox("Reporting Month", month_list)
selected_district = st.sidebar.selectbox("District Name", district_list)
facility_code = st.sidebar.text_input("Facility Code", placeholder="e.g., 44151234")

if st.sidebar.columns([2, 1.5])[1].button("🔍 Search", use_container_width=True):
    st.sidebar.success("Filters applied globally!")

st.sidebar.markdown("---")
admin_password = st.sidebar.text_input("🔒 Admin Access", type="password",
                                       help="Enter master password to unlock Admin tab")
try:
    current_db_password = con.execute(
        "SELECT setting_value FROM admin_settings WHERE setting_name = 'admin_password'").fetchone()[0]
except Exception:
    current_db_password = "admin"
is_admin = admin_password == current_db_password


# =====================================================================
# ENGINE 1: SINGLE MONTH RULES
# =====================================================================
def run_anomaly_engine(sel_fy, sel_month, sel_dist, fac_code):
    rules = get_cached_rules()
    raw = apply_global_filters(get_cached_hmis_data(sel_fy), sel_month, sel_dist, fac_code)
    if raw.empty or rules.empty:
        return pd.DataFrame()

    anomalies = []
    for _, rule in rules.iterrows():
        kind = rule.get("Rule_Category", rule.get("Rule_Type", "Math"))
        if kind not in ("Math", "Single Month"):
            continue
        try:
            hits, _, missing = evaluate_rule(rule, raw)
        except Exception:
            continue
        if missing or hits.empty:
            continue
        for _, row in hits.iterrows():
            anomalies.append({**{c: row[c] for c in BASE_COLS},
                              "Rule_ID": rule["Rule_ID"],
                              "Anomaly Type": rule["Rule_Description"],
                              "Error Count": 1})
    return pd.DataFrame(anomalies)


# =====================================================================
# ENGINE 2: MONTH-OVER-MONTH TREND PATTERNS
# =====================================================================
def run_trend_engine(sel_fy, sel_dist, fac_code):
    rules = get_cached_rules()
    data = get_cached_hmis_data(sel_fy).copy()
    if data.empty or rules.empty or "Rule_Category" not in rules.columns:
        return pd.DataFrame()

    mom_rules = rules[rules["Rule_Category"] == "MoM Trend"]
    if mom_rules.empty:
        return pd.DataFrame()

    # Strict chronological ordering per facility
    data["Date_Parsed"] = pd.to_datetime(data["Month"], format="%b-%Y", errors="coerce")
    data = data.sort_values(by=["Facility Code", "Date_Parsed"])
    data = apply_global_filters(data, district=sel_dist, fac_code=fac_code)

    def record(row, rule, pattern, details):
        return {**{c: row[c] for c in BASE_COLS}, "Rule_ID": rule["Rule_ID"],
                "Anomaly Type": rule["Rule_Description"], "Pattern": pattern, "Details": details}

    def numeric(df, cols):
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    found = []
    for _, rule in mom_rules.iterrows():
        pattern = str(rule["Trend_Pattern"])
        window = int(rule["Trend_Window_Months"]) if pd.notna(rule.get("Trend_Window_Months")) else 1
        threshold = float(rule["Trend_Threshold"]) if pd.notna(rule.get("Trend_Threshold")) else 0.0

        df = apply_rule_scope(data, rule)
        if df.empty:
            continue
        df = df.copy()
        group = lambda col: df.groupby("Facility Code")[col]  # noqa: E731

        # --- PATTERN 1: SUDDEN SPIKES ---
        if "Sudden Spike" in pattern:
            metric = str(rule["Logic_LHS"]).strip("[]")
            if metric not in df.columns:
                continue
            numeric(df, [metric])
            # Historical average EXCLUDING the current month
            df["Historical_Avg"] = group(metric).transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).mean())
            hits = df[(df[metric] > df["Historical_Avg"] * threshold) & (df["Historical_Avg"] > 0)]
            found += [record(r, rule, "Spike",
                             f"Value {r[metric]} is {threshold}x higher than historical avg "
                             f"{round(r['Historical_Avg'], 1)}") for _, r in hits.iterrows()]

        # --- PATTERN 2: REPEATED CONSTANTS (FLATLINES) ---
        elif "Repeated Constant" in pattern:
            metric = str(rule["Logic_LHS"]).strip("[]")
            if metric not in df.columns:
                continue
            numeric(df, [metric])
            df["R_Min"] = group(metric).transform(lambda x: x.rolling(window).min())
            df["R_Max"] = group(metric).transform(lambda x: x.rolling(window).max())
            hits = df[(df["R_Min"] == df["R_Max"]) & (df[metric] > 0)]
            found += [record(r, rule, "Flatline",
                             f"Value {r[metric]} copy-pasted for {window} consecutive months")
                      for _, r in hits.iterrows()]

        # --- PATTERN 3: CATEGORY SHIFT (ZERO-TO-MAX) ---
        elif "Category Shift" in pattern:
            metrics = re.findall(r"\[(.*?)\]", str(rule["Logic_LHS"]))
            if len(metrics) != 2 or not all(m in df.columns for m in metrics):
                continue
            sub, total = metrics
            numeric(df, [sub, total])
            df["Hist_Max"] = group(sub).transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).max())
            df["Current_Share"] = (df[sub] / df[total].replace(0, 1)) * 100
            hits = df[(df["Hist_Max"] == 0) & (df["Current_Share"] >= threshold) & (df[total] > 0)]
            found += [record(r, rule, "Category Shift",
                             f"Historically 0, but suddenly jumped to {round(r['Current_Share'], 1)}% "
                             f"of total ({r[sub]}/{r[total]})") for _, r in hits.iterrows()]

        # --- PATTERN 4: MULTI-INDICATOR COPY-PASTE ---
        elif "Copy-Paste" in pattern:
            metrics = list(dict.fromkeys(re.findall(r"\[(.*?)\]", str(rule["Logic_LHS"]))))
            valid = [m for m in metrics if m in df.columns]
            if len(valid) < 2:
                continue
            numeric(df, valid)
            df["Min_Val"], df["Max_Val"] = df[valid].min(axis=1), df[valid].max(axis=1)
            hits = df[(df["Min_Val"] == df["Max_Val"]) & (df["Max_Val"] > 0)]
            found += [record(r, rule, "Copy-Paste",
                             f"Value {r['Max_Val']} was copy-pasted across {len(valid)} "
                             f"different indicators") for _, r in hits.iterrows()]

    return pd.DataFrame(found)


# =====================================================================
# DRILL-DOWN MODAL
# =====================================================================
@st.dialog("🔍 Deep-Dive Analysis Mode", width="large")
def show_drilldown_modal(anomaly, raw_df):
    st.markdown(f"<h4 style='color:#d32f2f; margin-top:-10px; margin-bottom:20px;'>{anomaly}</h4>",
                unsafe_allow_html=True)
    try:
        info = con.execute("SELECT * FROM rules_metadata_v3 WHERE Rule_Description = ?", [anomaly]).fetchdf()
        if info.empty:
            st.error("Rule metadata missing.")
            return

        hits, metrics, _ = evaluate_rule(info.iloc[0], raw_df)
        if hits.empty:
            st.info("No detailed data found for this rule under current filters.")
            return

        detail = hits[detail_columns(hits, metrics)].copy()
        detail.insert(0, "S.No", range(1, len(detail) + 1))

        card = ("background-color:#f8f9fa; border-left:4px solid #ff5722; padding:10px;"
                " border-radius:5px; text-align:center; margin-bottom:15px;")
        cards = [("Total Errors", len(detail), "#d32f2f"),
                 ("Affected Facilities", detail["Facility Code"].nunique(), "#1976d2"),
                 ("Affected Districts", detail["District Name"].nunique(), "#388e3c")]
        for col, (label, value, color) in zip(st.columns(3), cards):
            col.markdown(f'<div style="{card}"><div style="font-size:12px; color:#555;">{label}</div>'
                         f'<div style="font-size:22px; font-weight:bold; color:{color};">{value:,}</div>'
                         f'</div>', unsafe_allow_html=True)

        show_grid(detail, [("S.No", {"width": 70, "pinned": "left"})], height=400, key="modal_grid")
        st.download_button("📥 Download Detailed Report", detail.to_csv(index=False).encode("utf-8"),
                           file_name="Anomaly_Deep_Dive.csv", mime="text/csv",
                           type="primary", use_container_width=True)
    except Exception as e:
        st.error(f"Error generating detailed view: {e}")


# =====================================================================
# HEADER + TAB LAYOUT
# =====================================================================
st.markdown('<div class="ds-yellow-header">HMIS DATA VALIDATION DASHBOARD, ANDHRA PRADESH</div>',
            unsafe_allow_html=True)
st.write("")

tab_names = ["📊 HMIS Dash Board", "📑 Single Month Anomalies", "📈 MoM Trend Anomalies",
             "📜 Rules Dictionary", "📖 Indicators List"]
if is_admin:
    tab_names += ["🏥 Facility wise anomalies", "🎯 Detailed Anomalies", "⚙️ Admin"]

tabs = st.tabs(tab_names)
tab_dash, tab_single, tab_mom, tab_rules, tab_indicators = tabs[:5]

master_anomalies_df = run_anomaly_engine(financial_year, selected_month, selected_district, facility_code)


# =====================================================================
# TAB 1: DASHBOARD
# =====================================================================
with tab_dash:
    if not master_anomalies_df.empty:
        total_anomalies = len(master_anomalies_df)
        facilities_count = master_anomalies_df["Facility Code"].nunique()
        rules_triggered = master_anomalies_df["Rule_ID"].nunique()
        df_districts = master_anomalies_df.groupby("District Name").size().reset_index(name="Error Count")
        df_top_rules = (master_anomalies_df.groupby("Anomaly Type").size()
                        .reset_index(name="Error Count").sort_values(by="Error Count", ascending=False))
        if "Facility Name" in master_anomalies_df.columns:
            priv_val = int(master_anomalies_df["Facility Name"]
                           .str.contains(PRIVATE_PATTERN, case=False, na=False).sum())
            pub_val = total_anomalies - priv_val
        else:
            pub_val, priv_val = total_anomalies, 0
    else:
        total_anomalies = facilities_count = rules_triggered = 0
        df_districts = pd.DataFrame({"District Name": ["No Data"], "Error Count": [0]})
        df_top_rules = pd.DataFrame({"Anomaly Type": ["No Errors"], "Error Count": [0]})
        pub_val, priv_val = 1, 0

    density = round(total_anomalies / facilities_count, 1) if facilities_count else 0

    tiles = [
        ("Total Anomalies", f"{total_anomalies:,}", "#d32f2f", "🔼 Live Engine Count", "#d32f2f", True),
        ("Facilities With Errors", f"{facilities_count:,}", "#ff9800", "Requiring Intervention", "#6c757d", False),
        ("Error Density", density, "#1976d2", "Avg Errors per Facility", "#6c757d", False),
        ("Rules Triggered", rules_triggered, "#9c27b0", "Unique Logic Failures", "#6c757d", False),
    ]
    for col, args in zip(st.columns(4), tiles):
        with col:
            kpi_tile(*args)

    st.divider()
    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        st.markdown('<div class="chart-title">DISTRICT WISE ANOMALIES HEAT MAP</div>', unsafe_allow_html=True)
        fig_bar = px.bar(df_districts, x="Error Count", y="District Name", orientation="h",
                         color_discrete_sequence=["#4285F4"], text="Error Count")
        fig_bar.update_traces(textposition="inside", insidetextanchor="middle", textangle=0,
                              textfont=dict(size=18, color="white", family="Arial Black"))
        fig_bar.update_layout(
            yaxis=dict(categoryorder="total ascending",
                       tickfont=dict(size=14, color="black", family="Arial Black")),
            height=max(380, len(df_districts) * 35), margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        # Fixed container forces scrolling instead of stretching the page
        with st.container(height=400):
            st.plotly_chart(fig_bar, use_container_width=True)
        total_bar("Grand total", total_anomalies)

    with col_right:
        st.markdown('<div class="chart-title">PUBLIC / PRIVATE %</div>', unsafe_allow_html=True)
        fig_pie = px.pie(pd.DataFrame({"Sector": ["Public", "Private"], "Value": [pub_val, priv_val]}),
                         values="Value", names="Sector", color_discrete_sequence=["#4285F4", "#FF9900"])
        fig_pie.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10),
                              paper_bgcolor="rgba(0,0,0,0)",
                              legend=dict(font=dict(size=14, color="#333", family="Arial Black")))
        fig_pie.update_traces(textposition="inside", textinfo="percent",
                              textfont=dict(size=15, color="white", family="Arial Black"))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown('<div class="chart-title" style="margin-top: 10px;">TOP 10 ANOMALIES</div>',
                    unsafe_allow_html=True)
        if total_anomalies > 0 and not df_top_rules.empty:
            top_10 = df_top_rules.head(10).copy()
            # Short label for the legend, wrapped full text for the hover box
            top_10["Short Rule"] = top_10["Anomaly Type"].apply(
                lambda x: str(x).split(" ")[0] if "-" in str(x) else str(x)[:15])
            top_10["Wrapped"] = top_10["Anomaly Type"].apply(
                lambda x: "<br>".join(textwrap.wrap(str(x), width=45)))
            fig_donut = px.pie(top_10, values="Error Count", names="Short Rule", hole=0.5,
                               custom_data=["Wrapped"])
            fig_donut.update_traces(
                hovertemplate="<b style='font-size:13px;'>%{customdata[0]}</b><br><br>"
                              "<b>Errors:</b> %{value}<br><b>Share:</b> %{percent}<extra></extra>",
                hoverlabel=dict(align="left", font=dict(size=13)),
                textposition="inside", textinfo="percent",
                textfont=dict(size=13, color="white", family="Arial Black"))
        else:
            fig_donut = px.pie(pd.DataFrame({"Anomaly Type": ["No Errors"], "Error Count": [1]}),
                               values="Error Count", names="Anomaly Type", hole=0.5)
            fig_donut.update_traces(textinfo="none")

        fig_donut.update_layout(
            height=210, margin=dict(l=0, r=0, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0,
                        font=dict(size=12, color="#333", family="Arial Black")))
        st.plotly_chart(fig_donut, use_container_width=True)


# =====================================================================
# TAB 2: SINGLE MONTH ABSTRACT + DRILL-DOWN
# =====================================================================
with tab_single:
    st.markdown("""
        <div class="header-wrapper">
            📄 Anomalies Abstract Table:
            <span class="animated-instruction">👉 Click On Required Anomaly to get Detailed Report</span>
        </div>
    """, unsafe_allow_html=True)

    if master_anomalies_df.empty:
        st.success("✅ No anomalies found for the selected criteria. The Abstract is clear.")
    else:
        abstract_df = (master_anomalies_df.groupby("Anomaly Type").size()
                       .reset_index(name="Anomaly Count").sort_values(by="Anomaly Count", ascending=False))
        abstract_df.insert(0, "Sl No", range(1, len(abstract_df) + 1))

        download_csv(abstract_df, "Abstract_Anomalies.csv", key="dl_abs",
                     label="📥 Download Abstract to CSV", ratio=(5, 1.5))

        select_css = dict(GRID_CSS)
        select_css[".ag-row-selected .ag-cell"] = {"background-color": "#FFB74D !important",
                                                   "color": "#000000 !important",
                                                   "font-weight": "bold !important"}
        select_css[".ag-row-selected"] = {"border-bottom": "2px solid #E65100 !important"}

        response = show_grid(
            abstract_df,
            [("Sl No", {"width": 80, "maxWidth": 80, "pinned": "left", "suppressSizeToFit": True}),
             ("Anomaly Count", {"width": 150, "maxWidth": 150, "suppressSizeToFit": True}),
             ("Anomaly Type", WRAP_COL)],
            height=450, fit=True, key="abstract_main_grid", css=select_css,
            row_selection="single", update_mode="SELECTION_CHANGED")

        total_bar("Grand Total Anomalies", int(abstract_df["Anomaly Count"].sum()))

        selected = response.get("selected_rows")
        if selected is not None and len(selected) > 0:
            picked = selected.iloc[0]["Anomaly Type"] if isinstance(selected, pd.DataFrame) \
                else selected[0]["Anomaly Type"]
            # Anti-haunting lock: don't re-open the dialog for the same row on every rerun
            if st.session_state.get("modal_anomaly_lock") != picked:
                st.session_state["modal_anomaly_lock"] = picked
                show_drilldown_modal(picked, apply_global_filters(
                    get_cached_hmis_data(financial_year), selected_month, selected_district, facility_code))
        else:
            st.session_state["modal_anomaly_lock"] = None


# =====================================================================
# TAB 3: MoM TREND ANOMALIES
# =====================================================================
with tab_mom:
    st.markdown("## 📈 Month-over-Month (MoM) Trend Anomalies")
    st.markdown("Detects historical time-series issues: Sudden Spikes, Flatlining Data, "
                "Category Shifts, and Multi-Indicator Copy-Paste errors.")

    mom_df = run_trend_engine(financial_year, selected_district, facility_code)

    if mom_df.empty:
        st.success("✅ No historical trend anomalies detected under the current filters.")
    else:
        st.error(f"🚨 Detected {len(mom_df)} Trend Anomalies in {selected_district}")

        st.markdown("### 📊 Trend Abstract")
        mom_abstract = (mom_df.groupby(["Anomaly Type", "Pattern"]).size()
                        .reset_index(name="Error Count").sort_values(by="Error Count", ascending=False))
        mom_abstract.insert(0, "S.No", range(1, len(mom_abstract) + 1))
        show_grid(mom_abstract, height=300, fit=True)

        st.markdown("### 🎯 Detailed Facility Trend Log")
        mom_details = mom_df.copy()
        mom_details.insert(0, "S.No", range(1, len(mom_details) + 1))
        show_grid(mom_details,
                  [("S.No", {"width": 70, "pinned": "left"}),
                   ("Details", {"minWidth": 300, "wrapText": True, "autoHeight": True})],
                  height=500)

        st.download_button("📥 Download Trend Data", mom_details.to_csv(index=False).encode("utf-8"),
                           file_name="MoM_Trend_Anomalies.csv", mime="text/csv", type="primary")


# =====================================================================
# TAB 4: RULES DICTIONARY
# =====================================================================
with tab_rules:
    st.subheader("📜 Dictionary of Active Anomaly Rules")
    st.markdown("All Single Month Rules stored in Master Database:")
    try:
        dict_df = con.execute("""
            SELECT Category_Code, Rule_ID, Rule_Description, Target_Format, Logic_LHS, Operator, Logic_RHS
            FROM rules_metadata_v3
            WHERE Rule_Category = 'Single Month' OR Rule_Category IS NULL OR Rule_Type = 'Math'
        """).fetchdf()

        if dict_df.empty:
            st.info("No single-month rules found in the database.")
        else:
            download_csv(dict_df, "rules_dictionary.csv", key="dl_dict")
            show_grid(dict_df, [
                (lambda f: f in ("Category_Code", "Rule_ID", "Operator"),
                 {"width": 90, "maxWidth": 100, "suppressSizeToFit": True}),
                ("Target_Format", {"width": 130, "maxWidth": 150, "wrapText": True,
                                   "autoHeight": True, "suppressSizeToFit": True}),
                (lambda f: f in ("Rule_Description", "Logic_LHS", "Logic_RHS"),
                 {**WRAP_COL, "minWidth": 200}),
            ], height=600, fit=True)
    except Exception as e:
        st.error(f"Error loading rules: {e}")


# =====================================================================
# TAB 5: INDICATORS LIST
# =====================================================================
with tab_indicators:
    st.subheader("📖 Monthly Service Delivery Indicators Mapping by Format Type")
    st.markdown("This tab displays the static list of all HMIS Monthly Service Delivery indicator "
                "names and their respective format types.")
    try:
        df_ind = pd.read_excel("indicators_list.xlsx", header=1)
        download_csv(df_ind, "Indicators_List.csv", key="dl_ind")

        df_ind = df_ind.dropna(how="all", axis=1).fillna("").astype(str)
        if "S.No" not in df_ind.columns:
            df_ind.insert(0, "S.No", range(1, len(df_ind) + 1))

        show_grid(df_ind, [
            (lambda f: f not in ("S.No", "Category", "Data Item Code", "Data Item Name"),
             {"width": 85, "maxWidth": 100, "suppressSizeToFit": True}),
            (lambda f: f in ("Category", "Data Item Code"),
             {"width": 110, "maxWidth": 130, "suppressSizeToFit": True}),
            ("Data Item Name", {**WRAP_COL, "minWidth": 300}),
            ("S.No", {"width": 70, "maxWidth": 80, "pinned": "left", "suppressSizeToFit": True}),
        ], height=600, fit=True)
    except FileNotFoundError:
        st.info("ℹ️ System is waiting for the file. Please place your Excel file in the same folder "
                "as 'app.py' and name it exactly **indicators_list.xlsx**.")
    except Exception as e:
        st.error(f"Error loading the Excel file: {e}")


# =====================================================================
# ADMIN-ONLY TABS
# =====================================================================
if is_admin:
    tab_facility, tab_detail, tab_admin = tabs[5:]

    # ---------- TAB 6: FACILITY WISE ----------
    with tab_facility:
        st.subheader("🏢 Facility Wise Anomalies Table")
        if master_anomalies_df.empty:
            st.success("✅ No anomalies found for the selected criteria.")
        else:
            df_facility = master_anomalies_df.drop(columns=["Rule_ID"], errors="ignore")
            df_facility.insert(0, "S.No", range(1, len(df_facility) + 1))
            download_csv(df_facility, "Facility_Wise_Anomalies.csv", key="dl_fac",
                         label="📥 Download Facility Data to CSV")
            show_grid(df_facility, [("S.No", {"width": 80, "pinned": "left"})], height=500)

    # ---------- TAB 7: RULE EXECUTION VIEWER ----------
    with tab_detail:
        st.subheader("🎯 Interactive Anomaly Rule Execution Viewer")
        active_cat = st.selectbox("📌 Select Anomaly Category:", CATEGORIES, key="cat_tab4")
        cat_rules = con.execute("SELECT * FROM rules_metadata_v3 WHERE Category_Code = ?",
                                [active_cat]).fetchdf()

        if cat_rules.empty:
            st.info(f"No rules exist in category {active_cat} yet.")
        else:
            col_label, col_radio = st.columns([1.5, 8.5])
            col_label.markdown("<div style='margin-top:14px; font-size:16px; font-weight:bold;'>"
                               "🎯 Select Rule No:</div>", unsafe_allow_html=True)
            with col_radio:
                rule_id = st.radio("Select Rule", cat_rules["Rule_ID"].tolist(),
                                   horizontal=True, label_visibility="collapsed")

            rule = cat_rules[cat_rules["Rule_ID"] == rule_id].iloc[0]
            st.markdown(f"<div class='chart-title' style='background-color:#ffeeba;"
                        f" border-color:#ffdf7e; color:#856404; margin-top:5px; margin-bottom:5px;'>"
                        f"{rule['Rule_Description']}</div>", unsafe_allow_html=True)

            raw = apply_global_filters(get_cached_hmis_data(financial_year),
                                       selected_month, selected_district, facility_code)
            try:
                hits, metrics, missing = evaluate_rule(rule, raw)
            except Exception as e:
                st.error(f"Rule Evaluation Error: {e}")
                hits, metrics, missing = pd.DataFrame(), [], []

            if missing:
                st.error(f"Missing columns in uploaded data: {missing}")
            elif hits.empty:
                st.success("✅ No anomalies found for this specific rule and filter combination.")
            else:
                out = hits[detail_columns(hits, metrics)].copy()
                download_csv(out, "Detailed_Anomalies.csv", key="dl_detail")
                out.insert(0, "S.No", range(1, len(out) + 1))
                show_grid(out, [("S.No", {"width": 80, "pinned": "left"})], height=500)

    # ---------- TAB 8: ADMIN CONSOLE ----------
    def appender(box_key, picker_key):
        """Callback factory: append the picked metric to an LHS/RHS text box."""
        def callback():
            metric = st.session_state.get(picker_key)
            if metric and metric != PICK:
                st.session_state[box_key] = (st.session_state.get(box_key) or "") + f"[{metric}] "
        return callback

    def formula_builder(prefix, default_op=">"):
        """Metric search box + LHS/Operator/RHS editor. Returns (lhs, operator, rhs)."""
        st.info("💡 **Click the box below and start typing to search.** Then click to add it to your formula.")
        picker, lhs_key, rhs_key = f"helper_{prefix}", f"{prefix}_lhs", f"{prefix}_rhs"
        st.session_state.setdefault(lhs_key, "")
        st.session_state.setdefault(rhs_key, "")

        st.selectbox("🔍 Search & Select Metric Name (Type to search)", [PICK] + ALL_METRICS_LIST, key=picker)
        b1, b2 = st.columns(2)
        b1.button("➕ Add to LHS Box", key=f"btn_{lhs_key}",
                  on_click=appender(lhs_key, picker), use_container_width=True)
        b2.button("➕ Add to RHS Box", key=f"btn_{rhs_key}",
                  on_click=appender(rhs_key, picker), use_container_width=True)

        c_lhs, c_op, c_rhs = st.columns([4, 1, 4])
        with c_lhs:
            lhs = st.text_area("Left Hand Side (LHS)", key=lhs_key)
        with c_op:
            idx = OPERATORS.index(default_op) if default_op in OPERATORS else 0
            operator = st.selectbox("Operator", OPERATORS, index=idx, key=f"{prefix}_op")
        with c_rhs:
            rhs = st.text_area("Right Hand Side (RHS)", key=rhs_key)
        return lhs, operator, rhs

    def dimension_inputs(formats, prefix, phc_default="All", own_default="All"):
        """PHC area scope + non-PHC ownership selectors, shown only when relevant."""
        areas, owners = ["All", "Rural", "Urban"], ["All", "Public", "Private"]
        c1, c2 = st.columns(2)
        with c1:
            if "PHC Format" in formats or "All Formats" in formats:
                phc = st.selectbox("🏡 PHC Area Scope (Applies only to PHC)", areas,
                                   index=areas.index(phc_default) if phc_default in areas else 0,
                                   key=f"{prefix}_phc")
            else:
                phc = "All"
                st.caption("ℹ️ Area Scope inactive (PHC Format not selected).")
        with c2:
            if any(f in formats for f in NON_PHC_FORMATS):
                own = st.selectbox("🏥 Ownership (Applies only to Non-PHC)", owners,
                                   index=owners.index(own_default) if own_default in owners else 0,
                                   key=f"{prefix}_own")
            else:
                own = "All"
                st.caption("ℹ️ Ownership inactive (Only PHC Format selected).")
        return phc, own

    def rule_exists(cat, rule_id):
        return con.execute("SELECT COUNT(*) FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?",
                           [cat, rule_id]).fetchone()[0] > 0

    def insert_rule(values):
        con.execute(f"INSERT INTO rules_metadata_v3 VALUES ({', '.join(['?'] * 15)})", values)

    with tab_admin:
        st.subheader("🔒 State Admin & Database Access")
        admin_action = st.radio("Select Action",
                                ["🧮 Add New Rule", "✏️ Edit/Delete Rule",
                                 "📤 Upload HMIS Data", "🔑 Change Password"], horizontal=True)
        st.divider()

        if "admin_success" in st.session_state and admin_action in ("🧮 Add New Rule", "✏️ Edit/Delete Rule"):
            st.success(st.session_state.pop("admin_success"))

        # ================= UPLOAD DATA =================
        if admin_action == "📤 Upload HMIS Data":
            st.markdown("### 📤 Upload & Replace Raw Data")
            c_fy, c_mo = st.columns(2)
            with c_fy:
                upload_fy = st.selectbox("Select Financial Year for Upload:", ["2026-27"])
            with c_mo:
                upload_month = st.selectbox("Select Month for Upload:", [
                    "Apr-2026", "May-2026", "Jun-2026", "Jul-2026", "Aug-2026", "Sep-2026",
                    "Oct-2026", "Nov-2026", "Dec-2026", "Jan-2027", "Feb-2027", "Mar-2027"])

            st.warning(f"⚠️ **Target Month:** You are uploading data for **{upload_month} ({upload_fy})**. "
                       "This action will **DELETE** any existing old data for this specific month and "
                       "replace it with these new files.")
            force_rebuild = st.checkbox(
                "⚠️ Force Database Reset (Check this box to permanently fix the 'Missing Columns' error "
                "by wiping the corrupted schema)", value=True)

            uploaded_files = st.file_uploader("Upload raw monthly/annual HMIS data files (CSV/Excel)",
                                              type=["csv", "xlsx"], accept_multiple_files=True)

            if uploaded_files and st.button("🚀 Process & Replace Database", type="primary"):
                with st.spinner("Processing massive dataset... please wait."):
                    success_count = 0
                    for file in uploaded_files:
                        try:
                        # 1. Save file to the server's hard drive to bypass web memory limits
                            temp_file_path = f"temp_{file.name}"
                            with open(temp_file_path, "wb") as f:
                                f.write(file.getbuffer())
                        
                        # 2. Read from the hard drive (removed low_memory=False to save RAM)
                        df_raw = pd.read_csv(temp_file_path) if temp_file_path.endswith(".csv") \
                            else pd.read_excel(temp_file_path)
                            
                        # 3. Delete the temporary file to keep the server clean
                        import os
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)

                        # Header sanitiser: kill non-breaking spaces, stray and doubled whitespace
                            df_raw.columns = [re.sub(r"\s+", " ", str(c).replace("\xa0", " ").strip())
                                              for c in df_raw.columns]
                            df_raw["Financial_Year"] = upload_fy
                            df_raw["Month"] = upload_month
                            if "Facility Code" in df_raw.columns:
                                df_raw["Facility Code"] = df_raw["Facility Code"].astype(str)

                            try:
                                if force_rebuild and success_count == 0:
                                    con.execute("DROP TABLE IF EXISTS hmis_master_data")

                                current_cols = con.execute("DESCRIBE hmis_master_data").fetchdf()
                                if len(current_cols) < 50:
                                    # Old mock/placeholder table - rebuild from this file
                                    con.execute("DROP TABLE IF EXISTS hmis_master_data")
                                    con.execute("CREATE TABLE hmis_master_data AS SELECT * FROM df_raw")
                                else:
                                    if success_count == 0:
                                        con.execute("DELETE FROM hmis_master_data "
                                                    "WHERE Financial_Year = ? AND Month = ?",
                                                    [upload_fy, upload_month])
                                    db_columns = con.execute(
                                        "SELECT * FROM hmis_master_data LIMIT 0").fetchdf().columns
                                    for col in db_columns:
                                        if col not in df_raw.columns:
                                            df_raw[col] = None
                                    df_raw = df_raw[db_columns]
                                    con.execute("INSERT INTO hmis_master_data SELECT * FROM df_raw")
                            except Exception:
                                con.execute("CREATE TABLE hmis_master_data AS SELECT * FROM df_raw")

                            success_count += 1
                        except Exception as e:
                            st.error(f"❌ Error processing {file.name}: {e}")

                    if success_count:
                        st.success(f"✅ Successfully processed {success_count} new file(s) for "
                                   f"{upload_month} into the Master Database! "
                                   f"(Columns matched: {len(df_raw.columns)})")
                        st.balloons()
                        st.cache_data.clear()

        # ================= ADD NEW RULE =================
        elif admin_action == "🧮 Add New Rule":
            st.markdown("### 🛠️ Advanced Formula Engine")

            if st.session_state.pop("clear_add_form", False):
                for key in ("new_desc", "add_lhs", "add_rhs"):
                    st.session_state[key] = ""

            col_cat, col_id = st.columns([1, 1])
            with col_cat:
                new_cat = st.selectbox("Assign to Category", CATEGORIES, key="new_cat")

            # Auto-suggest the next free rule number inside the chosen category
            try:
                existing_ids = con.execute("SELECT Rule_ID FROM rules_metadata_v3 WHERE Category_Code = ?",
                                           [new_cat]).fetchdf()["Rule_ID"]
                numbers = [int(m.group()) for m in
                           (re.search(r"\d+$", str(r)) for r in existing_ids) if m]
                next_num = max(numbers) + 1 if numbers else 1
            except Exception:
                next_num = 1

            with col_id:
                new_id = st.text_input("Rule ID (Number)", value=str(next_num))

            target_formats = st.multiselect("Applies to Format Type(s)", FORMAT_OPTIONS,
                                            default=["All Formats"], key="new_fmt")
            phc_scope, ownership = dimension_inputs(target_formats, "add")

            st.session_state.setdefault("new_desc", "")
            new_desc = st.text_input("Rule Description", key="new_desc",
                                     placeholder="Briefly describe the anomaly...")
            rule_type = st.radio("Rule Type", ["Single Month Validation", "Month-over-Month Trend Validation"],
                                 horizontal=True, key="new_type")

            # ---------- SINGLE MONTH ----------
            if rule_type == "Single Month Validation":
                lhs_expr, operator, rhs_expr = formula_builder("add")

                if st.button("💾 Save Mathematical Rule", type="primary"):
                    if not new_id or not new_desc:
                        red("❌ Rule ID and Rule Description cannot be empty.")
                    elif rule_exists(new_cat, new_id):
                        red(f"❌ ERROR: Rule '{new_id}' exists!")
                    else:
                        try:
                            insert_rule([new_cat, new_id, new_desc, ", ".join(target_formats), "Math",
                                         lhs_expr, operator, rhs_expr, True,
                                         "Single Month", "None", phc_scope, ownership, 1, 0.0])
                            st.session_state.clear_add_form = True
                            st.session_state.admin_success = f"✅ Rule {new_id} saved successfully! Form cleared."
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")

            # ---------- MoM TREND ----------
            else:
                st.markdown("#### 📉 Trend Pattern Engine")
                trend_pattern = st.selectbox("Select Trend Pattern to Monitor", [
                    "⚡ Sudden Spike / Extreme Outlier",
                    "🔄 Repeated Constant Values / Flatline",
                    "⚠️ Category Shift / Zero-to-Max Anomaly",
                    "📋 Multi-Indicator Copy-Paste"])

                if "Sudden Spike" in trend_pattern:
                    st.info("💡 Search and select the metric to track for spikes.")
                    picked = st.selectbox("🔍 Target Indicator", [PICK] + ALL_METRICS_LIST, key="spike_metric")
                    c_w, c_t = st.columns(2)
                    with c_w:
                        trend_window = st.slider("Lookback Baseline Window (Months)", 2, 12, 6)
                    with c_t:
                        trend_threshold = st.number_input("Spike Multiplier (x historical avg)",
                                                          1.5, 20.0, 3.0, 0.5)
                    lhs_expr = f"[{picked}]" if picked != PICK else ""
                    operator, rhs_expr = ">", f"Moving_Avg({trend_window}M) * {trend_threshold}"

                elif "Repeated Constant" in trend_pattern:
                    st.info("💡 Search and select the metric to track for flatlining data.")
                    picked = st.selectbox("🔍 Target Indicator", [PICK] + ALL_METRICS_LIST, key="flat_metric")
                    trend_window = st.slider("Consecutive Months Required with Identical Value", 2, 12, 4)
                    trend_threshold = 0.0
                    lhs_expr = f"[{picked}]" if picked != PICK else ""
                    operator, rhs_expr = "==", f"LAG({trend_window}M Continuous Match)"

                elif "Category Shift" in trend_pattern:
                    st.info("💡 Select the sub-indicator and its parent total to check for sudden ratio shifts.")
                    c_s, c_p = st.columns(2)
                    with c_s:
                        sub_raw = st.selectbox("🔍 Sub-Indicator (Under-reported)",
                                               [PICK] + ALL_METRICS_LIST, key="cat_sub")
                    with c_p:
                        tot_raw = st.selectbox("🔍 Total / Parent Indicator",
                                               [PICK] + ALL_METRICS_LIST, key="cat_tot")
                    trend_window = st.slider("Historical Lookback Zero Window (Months)", 3, 12, 6)
                    trend_threshold = st.slider("Current Month Minimum Share (%)", 50, 100, 90)
                    sub_ind = f"[{sub_raw}]" if sub_raw != PICK else ""
                    tot_ind = f"[{tot_raw}]" if tot_raw != PICK else ""
                    lhs_expr = f"({sub_ind} / {tot_ind}) * 100" if sub_ind and tot_ind else ""
                    operator, rhs_expr = ">=", f"{trend_threshold}%"

                else:  # Multi-Indicator Copy-Paste
                    st.info("💡 Type or paste the indicators that should NOT match, separated by commas.")
                    lhs_expr = st.text_area("Indicators Expected to Differ",
                                            "[1.1.2], [1.2.4], [1.2.5], [1.2.7]")
                    trend_window, trend_threshold = 1, 0.0
                    operator, rhs_expr = "==", "All Values Identical"

                if st.button("💾 Save Trend Rule", type="primary"):
                    if not new_id or not new_desc or not lhs_expr or PICK in lhs_expr:
                        red("❌ Rule ID, Description, and valid Indicators are required.")
                    elif rule_exists(new_cat, new_id):
                        red(f"❌ ERROR: Rule '{new_id}' exists!")
                    else:
                        try:
                            insert_rule([new_cat, new_id, new_desc, ", ".join(target_formats), "Trend",
                                         lhs_expr, operator, rhs_expr, True,
                                         "MoM Trend", trend_pattern, phc_scope, ownership,
                                         int(trend_window), float(trend_threshold)])
                            st.session_state.clear_add_form = True
                            st.session_state.admin_success = \
                                f"✅ Trend Rule {new_id} saved successfully! Form cleared."
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")

        # ================= EDIT / DELETE RULE =================
        elif admin_action == "✏️ Edit/Delete Rule":
            st.markdown("### ✏️ Edit or Delete Existing Rules")

            edit_cat = st.selectbox("📌 Select Category to Edit/Delete From", CATEGORIES, key="edit_cat_select")
            try:
                ids = con.execute("SELECT Rule_ID FROM rules_metadata_v3 WHERE Category_Code = ?",
                                  [edit_cat]).fetchdf()["Rule_ID"].astype(str).tolist()
            except Exception:
                ids = []

            if not ids:
                st.info(f"No rules exist in category {edit_cat} yet.")
            else:
                rule_to_edit = st.selectbox("📌 Select Rule to Edit/Delete", ["-- Select a Rule --"] + ids)

                if rule_to_edit != "-- Select a Rule --":
                    details = con.execute(
                        "SELECT * FROM rules_metadata_v3 WHERE Category_Code = ? AND Rule_ID = ?",
                        [edit_cat, rule_to_edit]).fetchdf().iloc[0]

                    # Reload the form whenever a different rule is selected
                    tracking_key = f"{edit_cat}_{rule_to_edit}"
                    if st.session_state.get("current_edit_rule") != tracking_key:
                        st.session_state.current_edit_rule = tracking_key
                        st.session_state.edit_desc = str(details["Rule_Description"])
                        st.session_state.edit_lhs = str(details["Logic_LHS"])
                        st.session_state.edit_rhs = str(details["Logic_RHS"])

                    st.write(f"Modifying: Category **{edit_cat}** - Rule **{rule_to_edit}**")
                    edit_desc = st.text_input("Rule Description", key="edit_desc")

                    try:
                        preselected = [f.strip() for f in str(details["Target_Format"]).split(",")]
                    except Exception:
                        preselected = ["All Formats"]
                    edit_formats = st.multiselect("Applies to Format Type(s)", FORMAT_OPTIONS,
                                                  default=preselected, key="edit_fmt")
                    edit_phc, edit_own = dimension_inputs(
                        edit_formats, "edit",
                        str(details.get("PHC_Area_Scope", "All")), str(details.get("Non_PHC_Ownership", "All")))

                    edit_lhs, edit_op, edit_rhs = formula_builder("edit", str(details["Operator"]))

                    st.write("")
                    col_save, col_del = st.columns(2)

                    if col_save.button("💾 Save Changes", type="primary", use_container_width=True):
                        try:
                            con.execute("""
                                UPDATE rules_metadata_v3
                                SET Rule_Description = ?, Target_Format = ?, Logic_LHS = ?, Operator = ?,
                                    Logic_RHS = ?, PHC_Area_Scope = ?, Non_PHC_Ownership = ?
                                WHERE Category_Code = ? AND Rule_ID = ?
                            """, [edit_desc, ", ".join(edit_formats), edit_lhs, edit_op, edit_rhs,
                                  edit_phc, edit_own, edit_cat, rule_to_edit])
                            for key in ("edit_desc", "edit_lhs", "edit_rhs", "current_edit_rule"):
                                st.session_state.pop(key, None)
                            st.session_state.admin_success = \
                                f"✅ Rule {rule_to_edit} in {edit_cat} updated successfully!"
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating rule: {e}")

                    if col_del.button("🗑️ Permanently Delete Rule", use_container_width=True):
                        try:
                            con.execute("DELETE FROM rules_metadata_v3 "
                                        "WHERE Category_Code = ? AND Rule_ID = ?", [edit_cat, rule_to_edit])
                            for key in ("edit_desc", "edit_lhs", "edit_rhs", "current_edit_rule"):
                                st.session_state.pop(key, None)
                            st.session_state.admin_success = \
                                f"🗑️ Rule {rule_to_edit} in {edit_cat} deleted permanently!"
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting rule: {e}")

        # ================= CHANGE PASSWORD =================
        else:
            st.markdown("### 🔑 Change Admin Password")
            with st.form("change_password_form"):
                old_pwd = st.text_input("Current Password", type="password")
                new_pwd = st.text_input("New Password", type="password")
                confirm_pwd = st.text_input("Confirm New Password", type="password")
                st.write("")

                if st.form_submit_button("💾 Update Password", type="primary"):
                    if old_pwd != current_db_password:
                        st.error("❌ Current password is incorrect.")
                    elif new_pwd != confirm_pwd:
                        st.error("❌ New passwords do not match.")
                    elif len(new_pwd) < 5:
                        st.error("❌ Password must be at least 5 characters long.")
                    else:
                        try:
                            con.execute("UPDATE admin_settings SET setting_value = ? "
                                        "WHERE setting_name = 'admin_password'", [new_pwd])
                            st.success("✅ Password updated successfully! Please re-enter your new "
                                       "password in the sidebar to keep Admin access.")
                        except Exception as e:
                            st.error(f"Database error: {e}")
