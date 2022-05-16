import csv
from datetime import datetime

import pandas as pd
import streamlit as st

# from st_aggrid import AgGrid
# from st_aggrid.grid_options_builder import GridOptionsBuilder

st.set_page_config(layout="wide")


def local_css(file_name):
    with open(file_name) as f:
        st.markdown('<style>{}</style>'.format(f.read()), unsafe_allow_html=True)

local_css("style.css")


class VehicleJournalTable:
    ID = "id"
    VEHICLE_MODEL = "марка машини"
    LICENCE_PLATE = "номерний знак"
    GROUP_OF_OPERATION = "група експлуатації"
    VEHICLE_PURPOSE = "з якою метою призначається машина"
    ROUTE = "маршрут руху"
    RESPONSIBLE = "в чиє розпорядження"
    TIME_CHECK_OUT = "час виїзду"
    TIME_CHECK_IN = "час повернення"

    @classmethod
    def items(cls):
        return [
            cls.ID, cls.VEHICLE_MODEL,
            cls.LICENCE_PLATE, cls.GROUP_OF_OPERATION,
            cls.VEHICLE_PURPOSE, cls.ROUTE,
            cls.RESPONSIBLE,
            cls.TIME_CHECK_OUT, cls.TIME_CHECK_IN
        ]

    @classmethod
    def sizes(cls):
        return


    @classmethod
    def num_columns(cls):
        return len(cls.items())


class Buttons:
    CHECK_OUT = "Виїхала"
    CHECK_IN = "Повернулась"


columns = [
    VehicleJournalTable.ID,
    VehicleJournalTable.VEHICLE_MODEL,
    VehicleJournalTable.LICENCE_PLATE,
    VehicleJournalTable.GROUP_OF_OPERATION,
    VehicleJournalTable.VEHICLE_PURPOSE,
    VehicleJournalTable.ROUTE,
    VehicleJournalTable.RESPONSIBLE,
    Buttons.CHECK_OUT,
    VehicleJournalTable.TIME_CHECK_OUT,
    Buttons.CHECK_IN,
    VehicleJournalTable.TIME_CHECK_IN,
]

indexes = {c:i for i, c in enumerate(columns)}

containers_size = [1] * len(columns)

if 'events' not in st.session_state:
    st.session_state['events'] = []
events = st.session_state['events']

with open("vehicles.csv", "r", newline='') as csv_file:
    reader = csv.DictReader(csv_file)
    containers = st.columns(containers_size)
    for i, column in enumerate(columns):
        containers[i].write(column.capitalize())
    st.markdown("""---""")

    datetime_format = "%H:%M:%S %d.%m.%Y"
    for row in reader:
        containers = st.columns(containers_size)
        idx = row[VehicleJournalTable.ID]

        vehicle_present = True
        i = indexes[Buttons.CHECK_OUT]
        if containers[i].button(Buttons.CHECK_OUT, key=f"{Buttons.CHECK_OUT}:{idx}"):
            vehicle_present = False
            events.append([idx, datetime.now().strftime(datetime_format), None])

        i = indexes[Buttons.CHECK_IN]
        if containers[i].button(Buttons.CHECK_IN, key=f"{Buttons.CHECK_IN}:{idx}"):
            vehicle_present = True
            assert len(events) > 0
            target_event = events[-1]
            for i in range(len(events) - 1, 0):
                if events[i][0] == idx:
                    target_event = events[i]
                    break
            target_event[-1] = datetime.now().strftime(datetime_format)

        for column in VehicleJournalTable.items():
            i = indexes[column]
            if column == VehicleJournalTable.VEHICLE_MODEL:
                color = 'green' if vehicle_present else 'red'
                t = f"<div><span class='highlight {color}'>{row[column]}</span> </div>"
                containers[i].markdown(t, unsafe_allow_html=True)
            else:
                containers[i].write(row[column])
        st.markdown("""---""")


df = pd.DataFrame(events)
st.dataframe(df)
# add this

# table = pd.read_csv("vehicles.csv")
# gb = GridOptionsBuilder.from_dataframe(table)
# gb.configure_pagination()
# gridOptions = gb.build()

# AgGrid(table, gridOptions=gridOptions)