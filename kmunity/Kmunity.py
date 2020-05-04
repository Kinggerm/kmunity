#!/usr/bin/env python

"""
Download fastq files to calculate genome size and heterozygosity with gce
"""

from __future__ import print_function

import os
import sys
import glob
import subprocess as sps

import requests
import pandas as pd
import kmunity
from loguru import logger

from .Fetch import Search_SRR



class Kmunity:
    """
    By default it looks for software in your PATH. 

    Parameters
    ----------
    srr: (str or None)
        NCBI Run ID, e.g., SRR7811753. If None then a sample that does not yet
        exist in the database will be fetched from NCBI for the selected 
        database (db).

    db: (str)
        The database to which a sample belongs (currently supported includes
        mammals, birds, plants). If an 'srr' is entered it will be checked
        for appropriate inclusion in the database.

    workdir: (str):
        A temporary directory in which the downloaded data can be stored. This
        should have plenty of space available. kmunity will remove all files 
        downloaded to this location after finishing. 

    repo: (str)
        The kmunity git repository where current results are stored and where
        new results will be organized. Default is "./kmunity".
    """
    def __init__(self, srr=None, db="mammals", workdir="/tmp", repo="./kmunity"):

        # store args
        self.srr = srr
        self.db = db
        self.data = None
        self.repo = os.path.realpath(os.path.expanduser(repo))
        self.csv = os.path.join(self.repo, self.db, "database.csv")
        self.workdir = os.path.realpath(os.path.expanduser(workdir))
        self.srrdir = os.path.join(self.workdir, self.srr)
        self.logdir = os.path.join(self.repo, self.db, "logfiles") 
        self.logfile = os.path.join(self.logdir, "{}.log".format(self.srr))
        self._logger_set()

        # check kwargs: e.g., user-supplied binary paths
        self.binaries = {
            "prefetch": os.path.join(sys.prefix, "bin", "prefetch"),
            "fasterq-dump": os.path.join(sys.prefix, "bin", "fasterq-dump"),
            "kmerfreq": os.path.join(sys.prefix, "bin", "kmerfreq"),
            "gce": os.path.join(sys.prefix, "bin", "gce"),
        }

        # run checks on existing results, paths and binaries.
        self._path_check()
        self._query_ncbi()
        self._get_usergh()
        self._get_binary()




    def _logger_set(self):
        # add stdout logger
        config = {
            "handlers": [
                {
                    "sink": sys.stdout, 
                    "format": (
                        "{time:YYYY-MM-DD-hh:mm} | "
                        "<cyan>{function}</cyan> | "
                        "<level>{message}</level>"
                    ),
                    "level": "DEBUG",
                    },
                {
                    "sink": self.logfile,                   
                    "format": "{time:YYYY-MM-DD} | {function} | {message}",
                    "level": "INFO",
                    }
            ],
            "extra": {"user": "deren"}
        }
        logger.configure(**config)
        logger.enable("kmunity")

        # if logfile exists then report it
        if os.path.exists(self.logfile):

            if 0:
                # if completed file found
                logger.warning(
                    "A completed logfile exists for this accession from {}.\n"
                    "Look in the database file for results."
                )

            else:
                # if logfile is unfinished (not completed run) then remove file
                logger.debug("LOCAL SETUP --------------------")
                logger.debug(
                    'Previous local run {} unfinished. Clearing logfile.'
                    .format(self.srr))
                open(self.logfile, 'w').close()
                logger.debug("")




    def _path_check(self):
        """
        Store path locations and check for existing results.
        """
        # ensure repo path is correct
        assert os.path.exists(self.repo), (
            "'repo' path not found: {}".format(self.repo))
        assert os.path.exists(self.csv), (
            "'repo' path does not point to local kmunity repo: {}"
            .format(self.repo))

        # ensure workdir and logdir exist
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        if not os.path.exists(self.logdir):
            os.makedirs(self.logdir)

        # load existing database
        self.data = pd.read_csv(self.csv)

        logger.debug("LOCAL PATHS --------------------")
        logger.debug("workdir: {}".format(self.workdir))
        logger.debug("logfile: {}".format(self.logfile))
        logger.debug("database: {}".format(self.csv))
        logger.debug("")        


        # curdb = pd.read_csv(self.csv)
        # if not os.path.exists(self.kwargs['outdir']):
            # os.makedirs(self.kwargs['outdir'])




    def _query_ncbi(self):
        """
        Query NCBI to get info for user selected SRR accession, OR, to find
        an SRR accession from the selected database that is not yet in the 
        kmunity database.
        """
        # No user SRR supplied
        if self.srr is None:
            logger.error("No SRR option not yet supported.")
            raise NotImplementedError("No SRR option not yet supported.")

        # user SRR supplied
        else:
            # print a log header with info
            logger.warning("QUERY --------------------------")
            self.query = Search_SRR(self.srr)
            self.query.run()
            logger.info("database: {}".format(self.db))
            logger.info("organism: {}".format(self.query.org))
            logger.info("taxid: {}".format(self.query.tax))
            logger.info("biosample: {}".format(self.query.bio))
            logger.info("run: {}".format(self.query.run))
            logger.info("size (Gb): {}".format(self.query.bases))
            # logger.info("status: {}".format(bool(self.srr in self.data.Run))
            logger.info("")




    def _get_usergh(self):
        # get user
        user = "anonymous"
        try:
            cmd = ["git", "config", "--get", "user.name"]
            proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
            user = proc.communicate()[0].decode().strip()
        except Exception:
            pass
        logger.warning("CONTRIBUTOR --------------------")
        logger.info("GitHub user: {}".format(user))
        logger.info("")




    def _get_binary(self):
        """
        Hack to pull in binaries. TODO: replace with conda recipes.
        """
        # pull gce & kmer executables to workdir
        gce_url = "https://github.com/fanagislab/GCE/raw/master/gce-1.0.2/gce"
        kme_url = "https://github.com/fanagislab/GCE/raw/master/gce-1.0.2/kmerfreq"
        for url in [gce_url, kme_url]:
            res = requests.get(url, allow_redirects=True)
            exe = os.path.basename(url)
            outbin = os.path.join(self.workdir, exe)
            with open(outbin, 'wb') as out:
                out.write(res.content)
            self.binaries[exe] = outbin

            # ensure it is executable
            cmd = ['chmod', '+x', outbin]
            proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
            out = proc.communicate()

        # print software versions
        logger.warning("VERSIONS ------------------------")
        logger.info("kmunity: {}".format(kmunity.__version__))
        logger.info("prefetch: {}".format(self._xprefetch(True)))
        logger.info("fasterq-dump: {}".format(self._xfasterqd(True)))
        logger.info("kmerfreq: {}".format(self._xkmerfreq(True)))
        logger.info("gce: {}".format(self._xcall_gce(True)))
        logger.info("")

        # remove the log file if failed.



    def _xprefetch(self, version_only=False):

        if version_only:
            # print the version
            proc = sps.Popen(
                [self.binaries["prefetch"], "-V"], 
                stderr=sps.STDOUT, 
                stdout=sps.PIPE,
            )
            out = proc.communicate()
            if proc.returncode:
                logger.error("tool not found.")
            return out[0].decode().split()[-1]

        # log the command used to prefetch
        cmd = [
            self.binaries["prefetch"], self.srr, 
            "-O", self.workdir,
        ]
        logger.info("Executing: {}".format(" ".join(cmd)))

        # call execute        
        proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
        out = proc.communicate()
        if proc.returncode:
            raise Exception(out[0])

        # show file size result
        size = os.path.getsize(os.path.join(self.srrdir, self.srr + ".sra"))
        size = round(size / 1e9, 2)
        logger.success("Downloaded {} ({} Gb)".format(self.srr + ".sra", size))


    def _xfasterqd(self, version_only=False):

        if version_only:
            # print the version
            proc = sps.Popen(
                [self.binaries["fasterq-dump"], "-V"],
                stderr=sps.STDOUT, 
                stdout=sps.PIPE,
            )
            out = proc.communicate()[0].decode().split()[-1]
            return out

        # call the tool
        cmd = [
            self.binaries["fasterq-dump"], self.srr, 
            "-O", self.srrdir,
        ]
        null = ["{fasterq-dump}", self.srr, "-O", "{workdir}/" + self.srr]
        logger.info("Executing: {}".format(" ".join(null)))
        logger.debug("Executing: {}".format(" ".join(cmd)))
        proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
        out = proc.communicate()
        if proc.returncode:
            raise Exception(out[0])

        # write a tmp SRR.lib file
        libfile = os.path.join(self.srrdir, "{}_files.lib".format(self.srr))
        fastqs = glob.glob(os.path.join(self.srrdir, "*.fastq"))
        with open(libfile, 'w') as out:
            out.write("\n".join(fastqs))

        # show file size result
        f1 = self.srr + "_1.fastq"
        fastq1 = os.path.join(self.srrdir, f1)
        size1 = os.path.getsize(fastq1)
        size1 = round(size1 / 1e9, 2)

        f2 = self.srr + "_2.fastq"
        fastq2 = os.path.join(self.srrdir, f2)
        size2 = os.path.getsize(fastq2)
        size2 = round(size2 / 1e9, 2)

        logger.success("Fastq dumped {} ({} Gb)".format(f1, size1))
        logger.success("Fastq dumped {} ({} Gb)".format(f2, size2))



    def _xkmerfreq(self, version_only=False):

        if version_only:
            proc = sps.Popen(
                [self.binaries["kmerfreq"], "-h"],
                stderr=sps.STDOUT, 
                stdout=sps.PIPE,
            )
            out = proc.communicate()[0].decode().split("\n")
            out = [i for i in out if "Version" in i][0]
            vers = out.split()[-1]
            return vers


        # call the tool
        lib = os.path.join(self.srrdir, "{}_files.lib".format(self.srr))
        cmd = [
            self.binaries["kmerfreq"],
            "-k", "17",
            "-t", "4",
            "-p", os.path.join(self.srrdir, self.srr),
            lib,
        ]

        # do not log local files paths
        null = "{kmerfreq} -k 17 -t 4 -p {srrdir}/{srr} {srrdir}/{srr}_files.lib"
        logger.info("Executing: {}".format(null))
        logger.debug("Executing: {}".format(" ".join(cmd)))
        proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
        out = proc.communicate()
        if proc.returncode:
            raise Exception(out[0].decode())

        # log head results file
        resfile = self.srr + ".kmer.freq.stat"
        logger.success("Kmer counts complete: {}".format(resfile))

        # with open(os.path.join(self.srrdir, resfile), 'r') as indata:
            # logger.info("FILE CONTENTS:\n" + "".join(indata.read()))



    def _xcall_gce(self, version_only=False):

        if version_only:
            # print the version
            proc = sps.Popen(
                [self.binaries["gce"], "-V"],
                stderr=sps.STDOUT, 
                stdout=sps.PIPE,
            )
            out = proc.communicate()[0].decode().split("\n")
            out = [i for i in out if "Version" in i][0]
            vers = out.split()[-1]
            return vers

        # prerun commands including (sic) 
        resfile = os.path.join(self.srrdir, self.srr + ".kmer.freq.stat")
        cmd1 = ['cat', resfile]
        cmd2 = ['grep', '#Kmer indivdual number']
        null = 'cat {srrdir}/{srr}.kmer.freq.stat | grep #Kmer indiv'
        logger.info("Executing {}:".format(null))
        logger.debug("Executing: {}".format(" ".join(cmd1)))
        proc1 = sps.Popen(cmd1, stderr=sps.STDOUT, stdout=sps.PIPE)
        proc2 = sps.Popen(cmd2, stdin=proc1.stdout, stdout=sps.PIPE)
        out = proc2.communicate()
        if proc2.returncode:
            logger.error(out[0].decode())
        ikmer = out[0].decode().strip().split()[-1]
        logger.success("Kmer individual number: {}".format(ikmer))

        res2col = resfile + ".2colum"
        logger.info("Parsing 2-columns file to: {}".format(res2col))
        arr = pd.read_csv(resfile, skiprows=7, sep="\t", header=None)
        arr = arr.iloc[:, :2]
        arr.to_csv(res2col, index=False, sep="\t", header=None)

        # Run in homozygous mode
        logger.info("Running 'gce' in homozygous mode to estimate coverage")
        null = "{gce} -g " + ikmer + " -f {res.2col}"
        logger.info("Executing: {}".format(null))
        cmd = [
            self.binaries["gce"],
            "-g", ikmer,
            "-f", res2col,
        ]
        logger.debug(" ".join(cmd))
        proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
        self.gce1out = proc.communicate()
        if proc.returncode:
            logger.error(self.gce1out[0].decode())

        # write to a tmp file
        coverage = self.gce1out[0].decode().split("Final estimation table:")
        coverage = coverage[-1].strip().split("\n")
        logger.success("GCE H0 coverage depth: {}".format(coverage))

        # Run in heterozygous mode
        logger.info("Running 'gce' in heterozygous mode.")
        null = "{gce} -g " + ikmer + " -f {res.2col}"
        logger.info("Executing: {}".format(null))
        cmd = [
            self.binaries["gce"],
            "-g", ikmer,
            "-f", res2col,
        ]
        logger.debug(" ".join(cmd))
        proc = sps.Popen(cmd, stderr=sps.STDOUT, stdout=sps.PIPE)
        self.gce1out = proc.communicate()
        if proc.returncode:
            logger.error(self.gce1out[0].decode())

        # write to a tmp file
        coverage = self.gce1out[0].decode().split("Final estimation table:")
        coverage = coverage[-1].strip().split("\n")
        logger.success("GCE genome size: {}".format(coverage))
        logger.success("GCE heterozygosity: {}".format(coverage))
        logger.success("GCE coverage depth: {}".format(coverage))




    def parse_results(self):
        pass



    def run(self):

        logger.warning("RUNNING -------------------------")
        try:
            self._xprefetch()
            self._xfasterqd()
            self._xkmerfreq()
            self._xcall_gce()
            # self.parse_results()

        finally:
            logger.info("removing tmp workdir")
            self._clean_ups()





if __name__ == "__main__":

    # SRS3758609    Ursus americanus    9643    11  SRR7811753
    SRR = "SRR7811753"
    tool = Kmunity(SRR, workdir="/home/deren/Downloads/SRRHET")
    tool.run()
