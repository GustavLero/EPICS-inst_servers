import os
import re
from shutil import copyfile
from collections import OrderedDict
from xml.etree import ElementTree

from config.containers import Group
from xml_converter import ConfigurationXmlConverter

from config.constants import GRP_NONE, AUTOSAVE_NAME
from config.configuration import Configuration

FILENAME_BLOCKS = "blocks.xml"
FILENAME_GROUPS = "groups.xml"
FILENAME_IOCS = "iocs.xml"
FILENAME_SUBCONFIGS = "components.xml"


class ConfigurationFileManager(object):
    """Saves and loads configuration data from file"""
    @staticmethod
    def load_config(root_path, config_name, macros):
        """Loads the configuration from the specified folder"""
        configuration = Configuration(macros)
        config_folder = os.path.abspath(root_path) + "\\" + config_name
        path = os.path.abspath(config_folder)
        if not os.path.isdir(path):
            raise Exception("Configuration could not be found")

        # Create empty containers
        blocks = OrderedDict()
        groups = OrderedDict()
        subconfigs = OrderedDict()
        iocs = OrderedDict()

        #Make sure NONE group exists
        groups[GRP_NONE.lower()] = Group(GRP_NONE)

        #Open the block file first
        blocks_path = path + "/" + FILENAME_BLOCKS
        if os.path.isfile(blocks_path):
            root = ConfigurationFileManager.parse_xml_removing_namespace(blocks_path)
            ConfigurationXmlConverter.blocks_from_xml(root, blocks, groups)

        #Import the groups
        groups_path = path + "/" + FILENAME_GROUPS
        if os.path.isfile(groups_path):
            root = ConfigurationFileManager.parse_xml_removing_namespace(groups_path)
            ConfigurationXmlConverter.groups_from_xml(root, groups, blocks)

        #Import the IOCs
        iocs_path = path + "/" + FILENAME_IOCS
        if os.path.isfile(iocs_path):
            root = ConfigurationFileManager.parse_xml_removing_namespace(iocs_path)
            ConfigurationXmlConverter.ioc_from_xml(root, iocs)

        #Import the subconfigs
        subconfig_path = path + "/" + FILENAME_SUBCONFIGS
        if os.path.isfile(subconfig_path):
            root = ConfigurationFileManager.parse_xml_removing_namespace(subconfig_path)
            ConfigurationXmlConverter.subconfigs_from_xml(root, subconfigs)

        # Set properties in the config
        configuration.blocks = blocks
        configuration.groups = groups
        configuration.iocs = iocs
        configuration.subconfigs = subconfigs
        configuration.name = config_name.replace("\\", "")
        return configuration

    @staticmethod
    def parse_xml_removing_namespace(file_path):
        it = ElementTree.iterparse(file_path)
        for _, el in it:
            if ':' in el.tag:
                el.tag = el.tag.split('}',1)[1]
        return it.root


    @staticmethod
    def save_config(configuration, root_path, config_name):
        """Saves the current configuration with the specified name"""
        config_folder = os.path.abspath(root_path) + "\\" + config_name
        path = os.path.abspath(config_folder)
        if not os.path.isdir(path):
            #create the directory
            os.makedirs(path)

        if config_name != AUTOSAVE_NAME:
            #Create a copy of the previous save
            ConfigurationFileManager.backup_old_config_file(path, FILENAME_BLOCKS)
            ConfigurationFileManager.backup_old_config_file(path, FILENAME_GROUPS)
            ConfigurationFileManager.backup_old_config_file(path, FILENAME_IOCS)
            ConfigurationFileManager.backup_old_config_file(path, FILENAME_SUBCONFIGS)

        blocks_xml = ConfigurationXmlConverter.blocks_to_xml(configuration.blocks, configuration.macros)
        groups_xml = ConfigurationXmlConverter.groups_to_xml(configuration.groups)
        iocs_xml = ConfigurationXmlConverter.iocs_to_xml(configuration.iocs)
        try:
            subconfigs_xml = ConfigurationXmlConverter.subconfigs_to_xml(configuration.subconfigs)
        except:
            #Is a subconfig, so no subconfigs
            subconfigs_xml = ConfigurationXmlConverter.subconfigs_to_xml(dict())


        #Save blocks
        with open(path + '/' + FILENAME_BLOCKS, 'w') as f:
            f.write(blocks_xml)

        #Save groups
        with open(path + '/' + FILENAME_GROUPS, 'w') as f:
            f.write(groups_xml)

        #Save IOCs
        with open(path + '/' + FILENAME_IOCS, 'w') as f:
            f.write(iocs_xml)

        #Save subconfigs
        with open(path + '/' + FILENAME_SUBCONFIGS, 'w') as f:
            f.write(subconfigs_xml)

    @staticmethod
    def backup_old_config_file(path, name):
        if os.path.isfile(path + '/' + name):
            high = 0
            for f in os.listdir(path):
                m = re.match("^" + name + "\.(\d+)", f)
                if m:
                    index = int(m.groups()[0])
                    if high is None:
                        high = index
                    elif index > high:
                        high = index
            try:
                print "Creating backup copy of %s" % name
                copyfile(path + '/' + name, path + '/' + name + ".%s" % (high+1))
            except Exception as err:
                print "Could not create backup copy of %s. Reason %s" % (name, err)

    @staticmethod
    def subconfig_exists(root_path, name):
        print root_path
        if not os.path.isdir(root_path + '/' + name):
            raise Exception("Subconfig does not exist")