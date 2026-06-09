def create_svi(mls, vlan_id, gateway_cidr):
    """
    Crea una interfaz interna en el multilayer switch.
    Esa interfaz funciona como gateway de la VLAN.
    """
    intf_name = f'vlan{vlan_id}'

    mls.cmd(
        f'ovs-vsctl --may-exist add-port {mls.name} {intf_name} '
        f'tag={vlan_id} -- set interface {intf_name} type=internal'
    )

    mls.cmd(f'ip addr flush dev {intf_name}')
    mls.cmd(f'ip addr add {gateway_cidr} dev {intf_name}')
    mls.cmd(f'ip link set {intf_name} up')