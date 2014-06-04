#!/usr/bin/env python

# Copyright (C) 2011 by Benedict Paten (benedictpaten@gmail.com)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

""" Reports the state of your given job tree.
"""

import sys
import os

import xml.etree.cElementTree as ET
from xml.dom import minidom  # For making stuff pretty

from sonLib.bioio import logger
from sonLib.bioio import logFile

from sonLib.bioio import getBasicOptionParser
from sonLib.bioio import parseBasicOptions
from sonLib.bioio import TempFileTree

from jobTree.src.master import getEnvironmentFileName, getJobFileDirName
from jobTree.src.master import getStatsFileName, getConfigFileName

class JTTag(object):
    """ Convenience object that stores xml attributes as object attributes.
    """
    def __init__(self, tree):
        """ Given an ElementTree tag, build a convenience object.
        """
        for name in ["total_time", "median_clock", "total_memory",
                     "median_wait", "total_number", "average_time",
                     "median_memory", "min_number_per_slave", "average_wait",
                     "total_clock", "median_time", "min_time", "min_wait",
                     "max_clock", "max_wait", "total_wait", "min_clock",
                     "average_memory", "max_number_per_slave", "max_memory",
                     "average_memory", "max_number_per_slave", "max_memory",
                     "median_number_per_slave", "average_number_per_slave",
                     "max_time", "average_clock", "min_memory", "min_clock",
                     ]:
          setattr(self, name, self.__get(tree, name))
        self.name = tree.tag
    def __get(self, tag, name):
      if name in tag.attrib:
          value = tag.attrib[name]
      else:
          return float("nan")
      try:
          a = float(value)
      except ValueError:
          a = float("nan")
      return a

class ColumnWidths(object):
    """ Convenience object that stores the width of columns for printing.
    Helps make things pretty.
    """
    def __init__(self):
        self.count = 10
        self.min = 10
        self.med = 10
        self.ave = 10
        self.max = 10
        self.total = 10
    def title(self):
        """ Return the total printed length of this category item.
        """
        return self.min + self.med + self.ave + self.max + self.total

def initializeOptions(parser):
    ##########################################
    # Construct the arguments.
    ##########################################
    parser.add_option("--jobTree", dest="jobTree",
                      help="Directory containing the job tree")
    parser.add_option("--outputFile", dest="outputFile", default=None,
                      help="File in which to write results")
    parser.add_option("--raw", action="store_true", default=False,
                      help="output the raw xml data.")
    parser.add_option("--pretty", "--human", action="store_true", default=False,
                      help=("if not raw, prettify the numbers to be "
                            "human readable."))
    parser.add_option("--categories",
                      help=("comma separated list from [time, clock, wait, "
                            "memory]"))
    parser.add_option("--sortCategory", default="time",
                      help=("how to sort Target list. may be from [alpha, "
                            "time, clock, wait, memory, count]. "
                            "default=%(default)s"))
    parser.add_option("--sortField", default="med",
                      help=("how to sort Target list. may be from [min, "
                            "med, ave, max, total]. "
                            "default=%(default)s"))
    parser.add_option("--sortReverse", "--reverseSort", default=False,
                      action="store_true",
                      help="reverse sort order.")

def checkOptions(options, args, parser):
    """ Check options, throw parser.error() if something goes wrong
    """
    logger.info("Parsed arguments")
    assert len(args) <= 1  # Only jobtree may be specified as argument
    if len(args) == 1:  # Allow jobTree directory as arg
        options.jobTree = args[0]
    logger.info("Checking if we have files for job tree")
    if options.jobTree == None:
        parser.error("Specify --jobTree")
    if not os.path.exists(options.jobTree):
        parser.error("--jobTree %s does not exist"
                     % options.jobTree)
    if not os.path.isdir(options.jobTree):
        parser.error("--jobTree %s is not a directory"
                     % options.jobTree)
    if not os.path.isfile(getConfigFileName(options.jobTree)):
        parser.error("A valid job tree must contain the config file")
    if not os.path.isfile(getStatsFileName(options.jobTree)):
        parser.error("The job-tree was run without the --stats flag, "
                     "so no stats were created")
    defaultCategories = ["time", "clock", "wait", "memory"]
    if options.categories is None:
        options.categories = defaultCategories
    else:
        options.categories = options.categories.split(",")
    for c in options.categories:
        if c not in defaultCategories:
            parser.error("Unknown category %s. Must be from %s"
                         % (c, str(defaultCategories)))
    extraSort = ["count", "alpha"]
    if options.sortCategory is not None:
        if (options.sortCategory not in defaultCategories and
            options.sortCategory not in extraSort):
            parser.error("Unknown --sortCategory %s. Must be from %s"
                         % (options.sortCategory,
                            str(defaultCategories + extraSort)))
    sortFields = ["min", "med", "ave", "max", "total"]
    if options.sortField is not None:
        if (options.sortField not in sortFields):
            parser.error("Unknown --sortField %s. Must be from %s"
                         % (options.sortField, str(sortFields)))
    logger.info("Checked arguments")

def prettyXml(elem):
    """ Return a pretty-printed XML string for the ElementTree Element.
    """
    roughString = ET.tostring(elem, "utf-8")
    reparsed = minidom.parseString(roughString)
    return reparsed.toprettyxml(indent="  ")

def padStr(s, field=None):
    """ Pad the begining of a string with spaces, if necessary.
    """
    if field is None:
        return s
    else:
      if len(s) >= field:
          return s
      else:
          return " " * (field - len(s)) + s

def prettyMemory(k, field=None, isBytes=False):
    """ Given input k as kilobytes, return a nicely formatted string.
    """
    from math import floor
    if isBytes:
        k /= 1024
    if k < 1024:
        return padStr("%gK" % k, field)
    if k < (1024 * 1024):
        return padStr("%.1fM" % (k / 1024.0), field)
    if k < (1024 * 1024 * 1024):
        return padStr("%.1fG" % (k / 1024.0 / 1024.0), field)
    if k < (1024 * 1024 * 1024 * 1024):
        return padStr("%.1fT" % (k / 1024.0 / 1024.0 / 1024.0), field)
    if k < (1024 * 1024 * 1024 * 1024 * 1024):
        return padStr("%.1fP" % (k / 1024.0 / 1024.0 / 1024.0 / 1024.0), field)

def prettyTime(t, field=None):
    """ Given input t as seconds, return a nicely formatted string.
    """
    from math import floor
    pluralDict = {True: "s", False: ""}
    if t < 120:
        return padStr("%ds" % t, field)
    if t < 120 * 60:
        m = floor(t / 60.)
        s = t % 60
        return padStr("%dm%ds" % (m, s), field)
    if t < 25 * 60 * 60:
        h = floor(t / 60. / 60.)
        m = floor((t - (h * 60. * 60.)) / 60.)
        s = t % 60
        return padStr("%dh%gm%ds" % (h, m, s), field)
    if t < 7 * 24 * 60 * 60:
        d = floor(t / 24. / 60. / 60.)
        h = floor((t - (d * 24. * 60. * 60.)) / 60. / 60.)
        m = floor((t
                   - (d * 24. * 60. * 60.)
                   - (h * 60. * 60.))
                  / 60.)
        s = t % 60
        dPlural = pluralDict[d > 1]
        return padStr("%dday%s%dh%dm%ds" % (d, dPlural, h, m, s), field)
    w = floor(t / 7. / 24. / 60. / 60.)
    d = floor((t - (w * 7 * 24 * 60 * 60)) / 24. / 60. / 60.)
    h = floor((t
                 - (w * 7. * 24. * 60. * 60.)
                 - (d * 24. * 60. * 60.))
                / 60. / 60.)
    m = floor((t
                 - (w * 7. * 24. * 60. * 60.)
                 - (d * 24. * 60. * 60.)
                 - (h * 60. * 60.))
                / 60.)
    s = t % 60
    wPlural = pluralDict[w > 1]
    dPlural = pluralDict[d > 1]
    return padStr("%dweek%s%dday%s%dh%dm%ds" % (w, wPlural, d,
                                                dPlural, h, m, s), field)

def reportTime(t, options, field=None):
    """ Given t seconds, report back the correct format as string.
    """
    if options.pretty:
        return prettyTime(t, field=field)
    else:
        if field is not None:
            return "%*.2f" % (field, t)
        else:
            return "%.2f" % t

def reportMemory(k, options, field=None, isBytes=False):
    """ Given k kilobytes, report back the correct format as string.
    """
    if options.pretty:
        return prettyMemory(k, field=field, isBytes=isBytes)
    else:
        if isBytes:
            k /= 1024
        if field is not None:
            return "%*gK" % (field, k)
        else:
            return "%gK" % k

def reportNumber(n, options, field=None):
    """ Given n an integer, report back the correct format as string.
    """
    if field is not None:
        return "%*g" % (field, n)
    else:
        return "%g" % n

def refineData(root, options):
    """ walk the root and gather up the important bits.
    """
    slave = JTTag(root.find("slave"))
    target = JTTag(root.find("target"))
    targetTypesTree = root.find("target_types")
    targetTypes = []
    for child in targetTypesTree:
        targetTypes.append(JTTag(child))
    return root, slave, target, targetTypes

def sprintTag(key, tag, options, columnWidths=None):
    """ Print out a JTTag().
    """
    if columnWidths is None:
        columnWidths = ColumnWidths()
    header = "  %7s " % decorateTitle("Count", options)
    sub_header = "  %7s " % "n"
    tag_str = "  %s" % reportNumber(tag.total_number, options, field=7)
    out_str = ""
    if key == "target":
        out_str += " %-12s | %7s%7s%7s%7s\n" % ("Slave Jobs", "min",
                                           "med", "ave", "max")
        slave_str = "%s| " % (" " * 14)
        for t in [tag.min_number_per_slave, tag.median_number_per_slave,
                  tag.average_number_per_slave, tag.max_number_per_slave]:
            slave_str += reportNumber(t, options, field=7)
        out_str += slave_str + "\n"
    if "time" in options.categories:
        header += "| %*s " % (columnWidths.title(),
                              decorateTitle("Time", options))
        sub_header += decorateSubHeader("Time", columnWidths, options)
        tag_str += " | "
        for t, width in [(tag.min_time, columnWidths.min),
                         (tag.median_time, columnWidths.med),
                         (tag.average_time, columnWidths.ave),
                         (tag.max_time, columnWidths.max),
                         (tag.total_time, columnWidths.total)]:
            tag_str += reportTime(t, options, field=width)
    if "clock" in options.categories:
        header += "| %*s " % (columnWidths.title(),
                              decorateTitle("Clock", options))
        sub_header += decorateSubHeader("Clock", columnWidths, options)
        tag_str += " | "
        for t, width in [(tag.min_clock, columnWidths.min),
                         (tag.median_clock, columnWidths.med),
                         (tag.average_clock, columnWidths.ave),
                         (tag.max_clock, columnWidths.max),
                         (tag.total_clock, columnWidths.total)]:
            tag_str += reportTime(t, options, field=width)
    if "wait" in options.categories:
        header += "| %*s " % (columnWidths.title(),
                              decorateTitle("Wait", options))
        sub_header += decorateSubHeader("Wait", columnWidths, options)
        tag_str += " | "
        for t, width in [(tag.min_wait, columnWidths.min),
                         (tag.median_wait, columnWidths.med),
                         (tag.average_wait, columnWidths.ave),
                         (tag.max_wait, columnWidths.max),
                         (tag.total_wait, columnWidths.total)]:
            tag_str += reportTime(t, options, field=width)
    if "memory" in options.categories:
        header += "| %*s " % (columnWidths.title(),
                              decorateTitle("Memory", options))
        sub_header += decorateSubHeader("Memory", columnWidths, options)
        tag_str += " | "
        for t, width in [(tag.min_memory, columnWidths.min),
                         (tag.median_memory, columnWidths.med),
                         (tag.average_memory, columnWidths.ave),
                         (tag.max_memory, columnWidths.max),
                         (tag.total_memory, columnWidths.total)]:
            tag_str += reportMemory(t, options, field=width)
    out_str += header + "\n"
    out_str += sub_header + "\n"
    out_str += tag_str + "\n"
    return out_str

def decorateTitle(title, options):
    """ Add a marker to title if the title is sorted on.
    """
    if title.lower() == options.sortCategory:
        return "%s*" % title
    else:
        return title

def decorateSubHeader(title, columnWidths, options):
    """ Add a marker to the correct field if the title is sorted on.
    """
    if title.lower() != options.sortCategory:
        return "| %*s%*s%*s%*s%*s " % (columnWidths.min, "min",
                                       columnWidths.med, "med",
                                       columnWidths.ave, "ave",
                                       columnWidths.max, "max",
                                       columnWidths.total, "total")
    else:
        s = "| "
        for field, width in [("min", columnWidths.min),
                             ("med", columnWidths.med),
                             ("ave", columnWidths.ave),
                             ("max", columnWidths.max),
                             ("total", columnWidths.total)]:
            if options.sortField == field:
                s += "%*s*" % (width - 1, field)
            else:
                s += "%*s" % (width, field)
        s += " "
        return s

def get(tree, name):
    """ Return a float value attribute NAME from TREE.
    """
    if name in tree.attrib:
        value = tree.attrib[name]
    else:
        return float("nan")
    try:
        a = float(value)
    except ValueError:
        a = float("nan")
    return a

def sortTargets(targetTypes, options):
    """ Return a targetTypes all sorted.
    """
    longforms = {"med": "median",
                 "ave": "average",
                 "min": "min",
                 "total": "total",
                 "max": "max",}
    sortField = longforms[options.sortField]
    if options.sortCategory == "time":
        return sorted(
            targetTypes,
            key=lambda tag: getattr(tag, "%s_time" % sortField),
            reverse=options.sortReverse)
    elif options.sortCategory == "clock":
        return sorted(
            targetTypes,
            key=lambda tag: getattr(tag, "%s_clock" % sortField),
            reverse=options.sortReverse)
    elif options.sortCategory == "wait":
        return sorted(
            targetTypes,
            key=lambda tag: getattr(tag, "%s_wait" % sortField),
            reverse=options.sortReverse)
    elif options.sortCategory == "memory":
        return sorted(
            targetTypes,
            key=lambda tag: getattr(tag, "%s_memory" % sortField),
            reverse=options.sortReverse)
    elif options.sortCategory == "alpha":
        return sorted(
            targetTypes, key=lambda tag: tag.name,
            reverse=options.sortReverse)
    elif options.sortCategory == "count":
        return sorted(targetTypes, key=lambda tag: tag.total_number,
                      reverse=options.sortReverse)

def reportPrettyData(root, slave, target, target_types, options):
    """ print the important bits out.
    """
    out_str = "Batch System: %s\n" % root.attrib["batch_system"]
    out_str += ("Default CPU: %s  Default Memory: %s\n"
                "Job Time: %s  Max CPUs: %s  Max Threads: %s\n" % (
        reportNumber(get(root, "default_cpu"), options),
        reportMemory(get(root, "default_memory"), options, isBytes=True),
        reportTime(get(root, "job_time"), options),
        reportNumber(get(root, "max_cpus"), options),
        reportNumber(get(root, "max_threads"), options),
        ))
    out_str += ("Total Clock: %s  Total Runtime: %s\n" % (
        reportTime(get(root, "total_clock"), options),
        reportTime(get(root, "total_run_time"), options),
        ))
    target_types = sortTargets(target_types, options)
    columnWidths = computeColumnWidths(target_types, slave, target, options)
    out_str += "Slave\n"
    out_str += sprintTag("slave", slave, options, columnWidths=columnWidths)
    out_str += "Target\n"
    out_str += sprintTag("target", target, options, columnWidths=columnWidths)
    for t in target_types:
        out_str += " %s\n" % t.name
        out_str += sprintTag(t.name, t, options, columnWidths=columnWidths)
    return out_str

def computeColumnWidths(target_types, slave, target, options):
    """ Return a ColumnWidths() object with the correct max widths.
    """
    cw = ColumnWidths()
    for t in target_types:
        updateColumnWidths(t, cw, options)
    updateColumnWidths(slave, cw, options)
    updateColumnWidths(target, cw, options)
    return cw

def updateColumnWidths(tag, cw, options):
    """ Update the column width attributes for this tag"s fields.
    """
    if "time" in options.categories:
        for t, width in [(tag.min_time, "min"),
                         (tag.median_time, "med"),
                         (tag.average_time, "ave"),
                         (tag.max_time, "max"),
                         (tag.total_time, "total")]:
            s = reportTime(t, options, field=getattr(cw, width))
            if len(s.strip()) >= getattr(cw, width):
                setattr(cw, width, len(s) + 1)
    if "clock" in options.categories:
        for t, width in [(tag.min_clock, "min"),
                         (tag.median_clock, "med"),
                         (tag.average_clock, "ave"),
                         (tag.max_clock, "max"),
                         (tag.total_clock, "total")]:
            s= reportTime(t, options, field=getattr(cw, width))
            if len(s.strip()) >= getattr(cw, width):
                setattr(cw, width, len(s) + 1)
    if "wait" in options.categories:
        for t, width in [(tag.min_wait, "min"),
                         (tag.median_wait, "med"),
                         (tag.average_wait, "ave"),
                         (tag.max_wait, "max"),
                         (tag.total_wait, "total")]:
            s= reportTime(t, options, field=getattr(cw, width))
            if len(s.strip()) >= getattr(cw, width):
                setattr(cw, width, len(s) + 1)
    if "memory" in options.categories:
        for t, iwdth in [(tag.min_memory, "min"),
                         (tag.median_memory, "med"),
                         (tag.average_memory, "ave"),
                         (tag.max_memory, "max"),
                         (tag.total_memory, "total")]:
            s = reportMemory(t, options, field=getattr(cw, width))
            if len(s.strip()) >= getattr(cw, width):
                setattr(cw, width, len(s) + 1)

def buildElement(element, items, itemName):
    """ Create an element for output.
    """
    def __round(i):
        if i < 0:
            logger.debug("I got a less than 0 value: %s" % i)
            return 0.0
        return i
    itemTimes = [ __round(float(item.attrib["time"])) for item in items ]
    itemTimes.sort()
    itemClocks = [ __round(float(item.attrib["clock"])) for item in items ]
    itemClocks.sort()
    itemWaits = [ __round(__round(float(item.attrib["time"])) -
                          __round(float(item.attrib["clock"])))
                  for item in items ]
    itemWaits.sort()
    itemMemory = [ __round(float(item.attrib["memory"])) for item in items ]
    itemMemory.sort()
    assert len(itemClocks) == len(itemTimes)
    assert len(itemClocks) == len(itemWaits)
    if len(itemTimes) == 0:
        itemTimes.append(0)
        itemClocks.append(0)
        itemWaits.append(0)
        itemMemory.append(0)
    return ET.SubElement(
        element, itemName,
        {"total_number":str(len(items)),
         "total_time":str(sum(itemTimes)),
         "median_time":str(itemTimes[len(itemTimes)/2]),
         "average_time":str(sum(itemTimes)/len(itemTimes)),
         "min_time":str(min(itemTimes)),
         "max_time":str(max(itemTimes)),
         "total_clock":str(sum(itemClocks)),
         "median_clock":str(itemClocks[len(itemClocks)/2]),
         "average_clock":str(sum(itemClocks)/len(itemClocks)),
         "min_clock":str(min(itemClocks)),
         "max_clock":str(max(itemClocks)),
         "total_wait":str(sum(itemWaits)),
         "median_wait":str(itemWaits[len(itemWaits)/2]),
         "average_wait":str(sum(itemWaits)/len(itemWaits)),
         "min_wait":str(min(itemWaits)),
         "max_wait":str(max(itemWaits)),
         "total_memory":str(sum(itemMemory)),
         "median_memory":str(itemMemory[len(itemMemory)/2]),
         "average_memory":str(sum(itemMemory)/len(itemMemory)),
         "min_memory":str(min(itemMemory)),
         "max_memory":str(max(itemMemory))
         })

def createSummary(element, containingItems, containingItemName, getFn):
    itemCounts = [len(getFn(containingItem)) for
                  containingItem in containingItems]
    itemCounts.sort()
    if len(itemCounts) == 0:
        itemCounts.append(0)
    element.attrib["median_number_per_%s" %
                   containingItemName] = str(itemCounts[len(itemCounts) / 2])
    element.attrib["average_number_per_%s" %
                   containingItemName] = str(float(sum(itemCounts)) /
                                             len(itemCounts))
    element.attrib["min_number_per_%s" %
                   containingItemName] = str(min(itemCounts))
    element.attrib["max_number_per_%s" %
                   containingItemName] = str(max(itemCounts))

def getSettings(options):
    config_file = getConfigFileName(options.jobTree)
    stats_file = getStatsFileName(options.jobTree)
    try:
        config = ET.parse(config_file).getroot()
    except ET.ParseError:
        sys.stderr.write("The config file xml, %s, is empty.\n" % config_file)
        raise
    try:
        stats = ET.parse(stats_file).getroot()
    except ET.ParseError:
        sys.stderr.write("The job tree stats file is empty. Either the job "
                         "has crashed, or no jobs have completed yet.\n")
        sys.exit(0)
    return config, stats

def processData(config, stats, options):
    ##########################################
    # Collate the stats and report
    ##########################################
    if stats.find("total_time") == None:  # Hack to allow unfinished jobtrees.
        ET.SubElement(stats, "total_time", { "time":"0.0", "clock":"0.0"})

    collatedStatsTag = ET.Element(
        "collated_stats",
        {"total_run_time":stats.find("total_time").attrib["time"],
         "total_clock":stats.find("total_time").attrib["clock"],
         "batch_system":config.attrib["batch_system"],
         "job_time":config.attrib["job_time"],
         "default_memory":config.attrib["default_memory"],
         "default_cpu":config.attrib["default_cpu"],
         "max_cpus":config.attrib["max_cpus"],
         "max_threads":config.attrib["max_threads"] })

    # Add slave info
    slaves = stats.findall("slave")
    buildElement(collatedStatsTag, slaves, "slave")

    # Add aggregated target info
    targets = []
    for slave in slaves:
        targets += slave.findall("target")
    def fn4(job):
        return list(slave.findall("target"))
    createSummary(buildElement(collatedStatsTag, targets, "target"),
                  slaves, "slave", fn4)
    # Get info for each target
    targetNames = set()
    for target in targets:
        targetNames.add(target.attrib["class"])
    targetTypesTag = ET.SubElement(collatedStatsTag, "target_types")
    for targetName in targetNames:
        targetTypes = [ target for target in targets
                        if target.attrib["class"] == targetName ]
        targetTypeTag = buildElement(targetTypesTag, targetTypes, targetName)
    return collatedStatsTag

def reportData(xml_tree, options):
    # Now dump it all out to file
    if options.raw:
        out_str = prettyXml(xml_tree)
    else:
        root, slave, target, target_types = refineData(xml_tree, options)
        out_str = reportPrettyData(root, slave, target, target_types, options)
    if options.outputFile != None:
        fileHandle = open(options.outputFile, "w")
        fileHandle.write(out_str)
        fileHandle.close()
    # Now dump onto the screen
    print out_str

def main():
    """ Reports stats on the job-tree, use with --stats option to jobTree.
    """

    parser = getBasicOptionParser(
        "usage: %prog [--jobTree] JOB_TREE_DIR [options]", "%prog 0.1")
    initializeOptions(parser)
    options, args = parseBasicOptions(parser)
    checkOptions(options, args, parser)
    config, stats = getSettings(options)
    collatedStatsTag = processData(config, stats, options)
    reportData(collatedStatsTag, options)

def _test():
    import doctest
    return doctest.testmod()

if __name__ == "__main__":
    _test()
    main()
