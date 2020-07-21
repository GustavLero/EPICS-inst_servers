# This file is part of the ISIS IBEX application.
# Copyright (C) 2012-2016 Science & Technology Facilities Council.
# All rights reserved.
#
# This program is distributed in the hope that it will be useful.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License v1.0 which accompanies this distribution.
# EXCEPT AS EXPRESSLY SET FORTH IN THE ECLIPSE PUBLIC LICENSE V1.0, THE PROGRAM
# AND ACCOMPANYING MATERIALS ARE PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND.  See the Eclipse Public License v1.0 for more details.
#
# You should have received a copy of the Eclipse Public License v1.0
# along with this program; if not, you can obtain a copy from
# https://www.eclipse.org/org/documents/epl-v10.php or
# http://opensource.org/licenses/eclipse-1.0.php
from .forwarderconfig import ForwarderConfig
from confluent_kafka import Producer, Consumer, KafkaException
import uuid
from typing import List
from streaming_data_types.fbschemas.forwarder_config_update_rf5k.Protocol import (
    Protocol,
)


class ProducerWrapper:
    """
    A wrapper class for the kafka producer.
    """

    def __init__(
            self,
            server: str,
            config_topic: str,
            data_topic: str,
            epics_protocol: Protocol = Protocol.CA,
    ):
        self.topic = config_topic
        self.converter = ForwarderConfig(data_topic, epics_protocol)
        self._set_up_producer(server)

    def _set_up_producer(self, server: str):
        conf = {"bootstrap.servers": server}
        try:
            self.producer = Producer(**conf)

            if not self.topic_exists(self.topic, server):
                print(
                    "WARNING: topic {} does not exist. It will be created by default.".format(
                        self.topic
                    )
                )
        except KafkaException.args[0] == "_BROKER_NOT_AVAILABLE":
            print("No brokers found on server: " + server[0])
            quit()
        except KafkaException.args[0] == "_TIMED_OUT":
            print("No server found, connection error")
            quit()
        except KafkaException.args[0] == "_INVALID_ARG":
            print("Invalid configuration")
            quit()
        except KafkaException.args[0] == "_UNKNOWN_TOPIC":
            print(
                "Invalid topic, to enable auto creation of topics set"
                " auto.create.topics.enable to false in broker configuration"
            )
            quit()

    def add_config(self, pvs: List[str]):
        """
        Create a forwarder configuration to add more pvs to be monitored.

        :param pvs: A list of new PVs to add to the forwarder configuration.
        """
        message_buffer = self.converter.create_forwarder_configuration(pvs)
        self.producer.produce(self.topic, value=message_buffer)
        self.producer.flush()

    @staticmethod
    def topic_exists(topic_name: str, server: str) -> bool:
        conf = {"bootstrap.servers": server, "group.id": uuid.uuid4()}
        consumer = Consumer(**conf)
        try:
            consumer.subscribe([topic_name])
            consumer.close()
        except KafkaException as e:
            print("topic '{}' does not exist".format(topic_name))
            print(e)
            return False
        return True

    def remove_config(self, pvs: List[str]):
        """
        Create a forwarder configuration to remove pvs that are being monitored.

        :param pvs: A list of PVs to remove from the forwarder configuration.
        """
        message_buffer = self.converter.remove_forwarder_configuration(pvs)
        self.producer.produce(self.topic, value=message_buffer)
        self.producer.flush()

    def stop_all_pvs(self):
        """
        Sends a stop_all command to the forwarder to clear all configuration.
        """
        message_buffer = self.converter.remove_all_forwarder_configuration()
        self.producer.produce(self.topic, value=message_buffer)
        self.producer.flush()