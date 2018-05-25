# Ansible playbook to install MiaRec applications

Documentation: [Installation of MiaRec on Linux using Ansible](https://www.miarec.com/doc/administration-guide/doc918)


# Testing using Vagrant virtual box


## Start virtual machine:

    cd tests/centos7-all-in-one
    vagrant up
    
## [Optional] Edit version info in the inventory file (tests/centos7-all-in-one/hosts):

    [all:vars]
    ; -------------------------------
    ; Version of installed packages
    ; -------------------------------
    miarecweb_version   = x.x.x.x
    miarec_version      = x.x.x.x
    miarec_screen_version = x.x.x.x
   
## Provision virtual machine
   
    ansible-playbook -i tests/centos7-all-in-one/hosts prepare-hosts.yml
    ansible-playbook -i tests/centos7-all-in-one/hosts configure-firewall.yml
    ansible-playbook -i tests/centos7-all-in-one/hosts setup-miarec.yml   