# Ansible playbook to install MiaRec applications

## Requirements

- Ansible v.2 


## How it works

You can run Ansible locally on the same server where MiaRec software is to be deployed. 
Or you can run it from remote host.

**Figure 1. Run Ansible locally on the same host**

<pre>
    +--------------------------------------------------------+                                 
    |  SERVER                                                |                                 
    |  +----------------------+   +-----------------------+  |                                 
    |  |      Ansible         |   |    MiaRec software    |  |                                 
    |  +----------------------+   +-----------------------+  |                                 
    +--------------------------------------------------------+                 
</pre>

**Figure 2. Run Ansible remotely**

<pre>
     +------------------------+           +----------------------------+
     |     Ansible host       |---------->|         MiaRec host        |
     +------------------------+           +----------------------------+

</pre>

Running of Ansible remotely is required when you deploy MiaRec on multiple-servers using decoupled architecture. In this case, you can update multiple servers in one click (see the Figure 3).

**Figure 3. Run Ansible remotely to deploy multiple target servers simultaneously**

<pre>
                                        +-------------------+                   
                              +-------> | MiaRec (recorder) |                   
                              |         +-------------------+                   
                              |                                               
    +----------------+        |         +-------------------+                   
    |    Ansible     |--------+-------> |  MiaRecWeb host   |                   
    +----------------+        |         +-------------------+                   
                              |                                               
                              |         +-------------------+                   
                              +-------> |  PostgreSQL host  |                   
                                        +-------------------+   
</pre>

## Instructions

### Step 1. Install Ansible on the controller machine

Ansible requires Linux machine, but it works also on Windows 10 under Bash on Ubuntu on Windows environment (WSL).

You need to install Ansible software on the host, from which you will be executing playbooks (the controller machine).
This could be the same host where you plan to install MiaRec or remote host, for example, your machine.

Ansible can be installed via “pip”, the Python package manager. If ‘pip’ isn’t already available in your version of Python, you can get pip by:

``` bash
sudo easy_install pip
```

Then install Ansible with:

``` bash
sudo pip install ansible
```

### Step 2. Clone this repository

Use `git` to clone this repository to your controlle machine. If git is not present on your machine, then install it with `sudo yum install git` (RedHat/Centos) or `sudo apt-get install git` (Ubuntu).

``` bash
git clone https://github.com/miarec/ansible-miarec --recursive
cd ./ansible-miarec
```


### Step 3. Create `hosts` file

If you are running Ansible locally, then the file content should be:

```
# 'hosts' file
miarec ansible_connection=local
```

If you are running Ansible from the control machine over SSH, then the file content should be (replace ip-address with the correct one):

```
# 'hosts' file
miarec ansible_host=10.1.2.3 ansible_port=22 ansible_user=root
```

### Step 4. Run prepare-hosts.yml playbook to initial provision of server(s)

The playbook `prepare-hosts.yml` will install the required packages, like PostgreSQL database, Apache web server, Redis, Python, etc.
Normally you need to run this playbook only once when you prepare the system for MiaRec installation.

When running Ansible locally, then you can just run:

``` bash
ansible-playbook prepare-hosts.yml
```

In case of remote installation, it is necessary to establish trust relationships between the controller and target machines.
When speaking with remote machines, Ansible by default assumes you are using SSH keys. SSH keys are encouraged but password authentication can also be used where needed by supplying the option --ask-pass.

When using password authentication, you can run the following command and you will prompted to enter the password for SSH connection:

``` bash
ansible-playbook prepare-hosts.yml --ask-pass
```

When using SSH keys for authentication, you can simply run the following command:

``` bash
ansible-playbook prepare-hosts.yml
```

Instructions: [How to set up ssh keys](https://www.digitalocean.com/community/tutorials/how-to-set-up-ssh-keys--2)


### Step 5. Run setup-miarec.yml playbook to install or update MiaRec software

The playbook `setup-miarec.yml` will install the MiaRec software (recorder, web portal, etc.).
You need to run this playbook everytime you want to upgrade MiaRec to new version.

Inside this file you will find the version information for miarec components, like:

``` yaml
  vars:
    miarecweb_version: 6.0.0.54
    miarec_version: 6.0.0.10
```

You can edit these values to install the particular versions of MiaRec applications.

To install/update MiaRec, run the following command:

``` bash
ansible-playbook setup-miarec.yml
```

When using password authentication, then add `--ask-pass` to the above commmand.

### Step 6. Verify installation

Now you should be able to access MiaRec web portal using web browser.

It is recommended to reboot the target machine and verify that everything is up and running after system reboot.


