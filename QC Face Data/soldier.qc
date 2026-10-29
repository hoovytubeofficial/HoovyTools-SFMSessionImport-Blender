// Created by Crowbar 0.74

$modelname "player/hwm/soldier.mdl"

$upaxis Y

$model "soldier" "soldier_morphs_sfm.smd" {

	eyeball "eye_right" "bip_head" -1.240000 78.620015 3.090003 "eyeball_r" 1.4 4 "iris_unused" 0.6
	eyeball "eye_left" "bip_head" 1.240000 78.620015 3.090003 "eyeball_l" 1.4 -4 "iris_unused" 0.6


	flexfile "soldier_01.vta" 
	{
		defaultflex frame 0
		flexpair "BrowOutV_Frown_RaiseBrowIn" 1 frame 1
		flexpair "CheekV_SneerNose" 1 frame 2
		flexpair "CloseLidLo" 1 frame 3
		flexpair "CloseLidUp" 1 frame 4
		flexpair "Frown_WrinkleNose" 1 frame 5
		flexpair "InnerSquint_OuterSquint" 1 frame 6
		flexpair "InnerSquint" 1 frame 7
		flexpair "OuterSquint" 1 frame 8
		flex "PuckerLips_RaiseChin_SneerNose" frame 9
		flexpair "ScalpForward" 1 frame 10
		flexpair "SmileFlat" 1 frame 11
		flexpair "SneerNose" 1 frame 12
		flexpair "WrinkleNose" 1 frame 13
		flexpair "BrowOutV_InnerSquint_OuterSquint" 1 frame 14
		flexpair "Frown_RaiseBrowIn" 1 frame 15
		flexpair "CloseLidUp_OuterSquint" 1 frame 16
		flexpair "CloseLidUp_InnerSquint" 1 frame 17
		flexpair "CloseLidUp_InnerSquint_OuterSquint" 1 frame 18
		flexpair "InnerSquint_SneerNose" 1 frame 19
		flexpair "InnerSquint_OuterSquint_SneerNose" 1 frame 20
		flexpair "PuckerLipUp_RaiseChin_SneerNose" 1 frame 21
		flexpair "BlowNostril" 1 frame 22
		flexpair "BrowOutV_RaiseBrowIn" 1 frame 23
		flexpair "BrowOutV" 1 frame 24
		flex "CheekV_PuckerLips" frame 25
		flexpair "CheekV_SmileFull" 1 frame 26
		flexpair "CheekV" 1 frame 27
		flex "ClenchJaw" frame 28
		flexpair "CompressLips_RaiseChin" 1 frame 29
		flexpair "CompressLips" 1 frame 30
		flexpair "DeflateCheek" 1 frame 31
		flexpair "Dimple_OpenLips" 1 frame 32
		flex "Dimple_PuckerLips" frame 33
		flexpair "Dimple" 1 frame 34
		flexpair "Frown" 1 frame 35
		flexpair "InflateCheek" 1 frame 36
		flex "JutJaw" frame 37
		flexpair "JutUpperLip_RaiseChin" 1 frame 38
		flexpair "JutUpperLip" 1 frame 39
		flexpair "LipCnrTwst_OpenUpperLip_SuckLipLo" 1 frame 40
		flexpair "LipCnrTwst" 1 frame 41
		flexpair "OpenJaw_OpenLips" 1 frame 42
		flexpair "OpenJaw_OpenLowerLip_OpenUpperLip_Platysmus_SmileFull" 1 frame 43
		flexpair "OpenJaw_OpenLowerLip_OpenUpperLip" 1 frame 44
		flex "OpenJaw" frame 45
		flexpair "OpenLips_SmileFull" 1 frame 46
		flexpair "OpenLips" 1 frame 47
		flexpair "OpenLowerLip_OpenUpperLip_Platysmus_SmileFull" 1 frame 48
		flexpair "OpenLowerLip_OpenUpperLip" 1 frame 49
		flexpair "OpenLowerLip_SuckLipLo" 1 frame 50
		flexpair "OpenLowerLip" 1 frame 51
		flexpair "OpenUpperLip_SuckLipUp" 1 frame 52
		flexpair "OpenUpperLip" 1 frame 53
		flexpair "Platysmus" 1 frame 54
		flexpair "PressNose" 1 frame 55
		flex "PuckerLips_RaiseChin" frame 56
		flexpair "RaiseBrowIn" 1 frame 57
		flexpair "RaiseChin" 1 frame 58
		flexpair "ScalpBack" 1 frame 59
		flexpair "SmileFull" 1 frame 60
		flexpair "SmileSharp" 1 frame 61
		flex "SuckJaw" frame 62
		flexpair "SuckLipLo" 1 frame 63
		flexpair "SuckLipUp" 1 frame 64
		flexpair "SuckNostril" 1 frame 65
		flexpair "CheekV_OuterSquint" 1 frame 66
		flexpair "CheekV_InnerSquint" 1 frame 67
		flexpair "CheekV_InnerSquint_OuterSquint" 1 frame 68
		flexpair "BrowOutV_InnerSquint" 1 frame 69
		flexpair "BrowOutV_OuterSquint" 1 frame 70
		flexpair "InnerSquint_RaiseBrowIn" 1 frame 71
		flexpair "CheekV_CloseLidLo" 1 frame 72
		flexpair "CloseLidUp_RaiseBrowIn" 1 frame 73
		flexpair "InnerSquint_OuterSquint_RaiseBrowIn" 1 frame 74
		flexpair "CloseLidUp_InnerSquint_OuterSquint_RaiseBrowIn" 1 frame 75
		flexpair "BrowOutV_CloseLidUp" 1 frame 76
		flexpair "BrowOutV_Frown" 1 frame 77
		flexpair "BrowOutV_CloseLidUp_RaiseBrowIn" 1 frame 78
		flexpair "BrowOutV_CloseLidUp_Frown" 1 frame 79
		flexpair "PuckerLipUp" 1 frame 80
		flexpair "PuckerLipLo" 1 frame 81
		flexpair "PuckerLipLo_PuckerLipUp" 1 frame 82
		flexpair "OpenJaw_PuckerLipUp" 1 frame 83
		flexpair "OpenJaw_PuckerLipLo" 1 frame 84
		flexpair "OpenJaw_PuckerLipLo_PuckerLipUp" 1 frame 85
		flexpair "OpenLips_PuckerLipUp" 1 frame 86
		flexpair "OpenLips_PuckerLipLo" 1 frame 87
		flexpair "OpenLips_PuckerLipLo_PuckerLipUp" 1 frame 88
		flexpair "OpenJaw_OpenLips_PuckerLipLo_PuckerLipUp" 1 frame 89
		flexpair "OpenJaw_OpenLips_PuckerLipLo" 1 frame 90
		flexpair "OpenJaw_OpenLips_PuckerLipUp" 1 frame 91
		flexpair "Dimple_PuckerLipLo" 1 frame 92
		flexpair "Dimple_PuckerLipUp" 1 frame 93
		flexpair "Dimple_PuckerLipLo_PuckerLipUp" 1 frame 94
		flexpair "Dimple_OpenLips_PuckerLipLo_PuckerLipUp" 1 frame 95
		flexpair "FunnelLipUp" 1 frame 96
		flexpair "FunnelLipLo" 1 frame 97
		flexpair "FunnelLipLo_FunnelLipUp" 1 frame 98
		flexpair "Dimple_FunnelLipLo" 1 frame 99
		flexpair "Dimple_FunnelLipUp" 1 frame 100
		flexpair "Dimple_FunnelLipLo_FunnelLipUp" 1 frame 101
		flexpair "FunnelLipUp_OpenJaw" 1 frame 102
		flexpair "FunnelLipLo_OpenJaw" 1 frame 103
		flexpair "FunnelLipLo_FunnelLipUp_OpenJaw" 1 frame 104
		flexpair "PuffLipUp" 1 frame 105
		flexpair "PuffLipLo" 1 frame 106
		flexpair "PuckerLipUp_RaiseChin" 1 frame 107
		flexpair "OpenLips_OpenUpperLip" 1 frame 108
		flexpair "OpenLips_OpenLowerLip" 1 frame 109
		flexpair "OpenJaw_OpenLips_OpenUpperLip" 1 frame 110
		flexpair "OpenJaw_OpenLips_OpenLowerLip" 1 frame 111
		flexpair "OpenJaw_OpenUpperLip" 1 frame 112
		flexpair "OpenJaw_OpenLowerLip" 1 frame 113
		flexpair "OpenUpperLip_Platysmus" 1 frame 114
		flexpair "OpenLowerLip_Platysmus" 1 frame 115
		flexpair "OpenLowerLip_OpenUpperLip_Platysmus" 1 frame 116
		flexpair "OpenUpperLip_SmileFull" 1 frame 117
		flexpair "OpenLowerLip_SmileFull" 1 frame 118
		flexpair "OpenLowerLip_OpenUpperLip_SmileFull" 1 frame 119
		flexpair "OpenLips_OpenUpperLip_SmileFull" 1 frame 120
		flexpair "OpenLips_OpenLowerLip_SmileFull" 1 frame 121
		flexpair "Platysmus_SmileFull" 1 frame 122
		flexpair "Platysmus_RaiseChin" 1 frame 123
		flexpair "JutUpperLip_Platysmus_RaiseChin" 1 frame 124
		flexpair "OpenUpperLip_Platysmus_SmileFull" 1 frame 125
		flexpair "OpenLowerLip_Platysmus_SmileFull" 1 frame 126
		flexpair "OpenJaw_Platysmus" 1 frame 127
		flexpair "OpenJaw_OpenLowerLip_Platysmus" 1 frame 128
		flexpair "OpenJaw_SmileFull" 1 frame 129
		flexpair "OpenJaw_Platysmus_SmileFull" 1 frame 130
		flexpair "OpenJaw_OpenLowerLip_SmileFull" 1 frame 131
		flexpair "OpenJaw_OpenUpperLip_SmileFull" 1 frame 132
		flexpair "OpenJaw_OpenLowerLip_OpenUpperLip_SmileFull" 1 frame 133
		flexpair "OpenJaw_OpenLowerLip_Platysmus_SmileFull" 1 frame 134
		flexpair "OpenJaw_OpenUpperLip_Platysmus" 1 frame 135
		flexpair "OpenJaw_OpenLowerLip_OpenUpperLip_Platysmus" 1 frame 136
		flexpair "OpenJaw_OpenUpperLip_Platysmus_SmileFull" 1 frame 137
		flex "SlideJawL" frame 138
		flex "SlideJawR" frame 139
		flexpair "CheekV_PuckerLipUp_RaiseChin" 1 frame 140
		flexpair "CompressLips_JutUpperLip_RaiseChin" 1 frame 141
		flex "TongueBack" frame 142
		flex "TongueCurlDown" frame 143
		flex "TongueCurlUp" frame 144
		flex "TongueFunnel" frame 145
		flex "TongueLeft" frame 146
		flex "TongueNarrow" frame 147
		flex "TongueOut" frame 148
		flex "TongueRight" frame 149
		flex "TongueV" frame 150
		flex "TongueWide" frame 151
		flex "TongueBack_TongueCurlDown_TongueV" frame 152
		flex "TongueBack_TongueCurlDown" frame 153
		flex "TongueBack_TongueV" frame 154
		flex "TongueCurlDown_TongueOut" frame 155
		flex "TongueCurlDown_TongueV" frame 156
		flex "TongueCurlUp_TongueOut_TongueV" frame 157
		flex "TongueCurlUp_TongueOut" frame 158
		flex "TongueCurlUp_TongueV" frame 159
		flex "TongueOut_TongueV" frame 160
	}

	flexcontroller right_CloseLid range -1 1 "right_CloseLid"
	flexcontroller left_CloseLid range -1 1 "left_CloseLid"
	flexcontroller multi_CloseLid range -1 1 "multi_CloseLid"
	flexcontroller blink range 0 1 "blink"
	flexcontroller right_InnerSquint range 0 1 "right_InnerSquint"
	flexcontroller left_InnerSquint range 0 1 "left_InnerSquint"
	flexcontroller right_OuterSquint range 0 1 "right_OuterSquint"
	flexcontroller left_OuterSquint range 0 1 "left_OuterSquint"
	flexcontroller right_BrowInV range -1 1 "right_BrowInV"
	flexcontroller left_BrowInV range -1 1 "left_BrowInV"
	flexcontroller right_BrowOutV range 0 1 "right_BrowOutV"
	flexcontroller left_BrowOutV range 0 1 "left_BrowOutV"
	flexcontroller right_Frown range 0 1 "right_Frown"
	flexcontroller left_Frown range 0 1 "left_Frown"
	flexcontroller right_NoseV range -1 1 "right_NoseV"
	flexcontroller left_NoseV range -1 1 "left_NoseV"
	flexcontroller right_NostrilFlare range -1 1 "right_NostrilFlare"
	flexcontroller left_NostrilFlare range -1 1 "left_NostrilFlare"
	flexcontroller right_CheekV range 0 1 "right_CheekV"
	flexcontroller left_CheekV range 0 1 "left_CheekV"
	flexcontroller right_CheekH range -1 1 "right_CheekH"
	flexcontroller left_CheekH range -1 1 "left_CheekH"
	flexcontroller JawD range -1 1 "JawD"
	flexcontroller JawH range -1 1 "JawH"
	flexcontroller JawV range -1 1 "JawV"
	flexcontroller right_LipsV range -1 1 "right_LipsV"
	flexcontroller left_LipsV range -1 1 "left_LipsV"
	flexcontroller right_LipUpV range -1 1 "right_LipUpV"
	flexcontroller left_LipUpV range -1 1 "left_LipUpV"
	flexcontroller right_LipLoV range -1 1 "right_LipLoV"
	flexcontroller left_LipLoV range -1 1 "left_LipLoV"
	flexcontroller right_Smile range 0 1 "right_Smile"
	flexcontroller left_Smile range 0 1 "left_Smile"
	flexcontroller multi_Smile range -1 1 "multi_Smile"
	flexcontroller right_Platysmus range 0 1 "right_Platysmus"
	flexcontroller left_Platysmus range 0 1 "left_Platysmus"
	flexcontroller right_FoldLipUp range -1 1 "right_FoldLipUp"
	flexcontroller left_FoldLipUp range -1 1 "left_FoldLipUp"
	flexcontroller right_FoldLipLo range -1 1 "right_FoldLipLo"
	flexcontroller left_FoldLipLo range -1 1 "left_FoldLipLo"
	flexcontroller right_PuckerLipUp range 0 1 "right_PuckerLipUp"
	flexcontroller left_PuckerLipUp range 0 1 "left_PuckerLipUp"
	flexcontroller right_PuckerLipLo range 0 1 "right_PuckerLipLo"
	flexcontroller left_PuckerLipLo range 0 1 "left_PuckerLipLo"
	flexcontroller right_LipCnrTwst range 0 1 "right_LipCnrTwst"
	flexcontroller left_LipCnrTwst range 0 1 "left_LipCnrTwst"
	flexcontroller right_Dimple range 0 1 "right_Dimple"
	flexcontroller left_Dimple range 0 1 "left_Dimple"
	flexcontroller right_PuffLipUp range 0 1 "right_PuffLipUp"
	flexcontroller left_PuffLipUp range 0 1 "left_PuffLipUp"
	flexcontroller right_PuffLipLo range 0 1 "right_PuffLipLo"
	flexcontroller left_PuffLipLo range 0 1 "left_PuffLipLo"
	flexcontroller right_ScalpD range -1 1 "right_ScalpD"
	flexcontroller left_ScalpD range -1 1 "left_ScalpD"
	flexcontroller TongueV range 0 1 "TongueV"
	flexcontroller TongueH range -1 1 "TongueH"
	flexcontroller TongueCurl range -1 1 "TongueCurl"
	flexcontroller TongueD range -1 1 "TongueD"
	flexcontroller TongueFunnel range 0 1 "TongueFunnel"
	flexcontroller TongueWidth range -1 1 "TongueWidth"
	flexcontroller eyes range -45 45 "eyes_updown"
	flexcontroller eyes range -45 45 "eyes_rightleft"

	%BlowNostrilL = (min(max(left_NostrilFlare, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BlowNostrilR = (min(max(right_NostrilFlare, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_Frown_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * left_Frown * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_Frown_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * right_Frown * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutVL = left_BrowOutV
	%BrowOutVR = right_BrowOutV
	%CheekV_SmileFullL = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_CheekV) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_SmileFullR = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_CheekV) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_SneerNoseL = ((min(max(left_NoseV, 0), 1)) * left_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_SneerNoseR = ((min(max(right_NoseV, 0), 1)) * right_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekVL = left_CheekV
	%CheekVR = right_CheekV
	%ClenchJaw = (1 - (min(max(JawV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidLoL = (min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidLoR = (min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUpL = (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUpR = (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLips_RaiseChinL = ((((((1 - (min(max(left_LipLoV + 1, 0), 1))) * (1 - (min(max(left_LipsV + 1, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLips_RaiseChinR = ((((((1 - (min(max(right_LipLoV + 1, 0), 1))) * (1 - (min(max(right_LipsV + 1, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLipsL = ((((1 - (min(max(left_LipsV + 1, 0), 1))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLipsR = ((((1 - (min(max(right_LipsV + 1, 0), 1))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DeflateCheekL = (1 - (min(max(left_CheekH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DeflateCheekR = (1 - (min(max(right_CheekH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_OpenLipsL = (((((min(max(left_LipsV, 0), 1)) * left_Dimple) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_OpenLipsR = (((((min(max(right_LipsV, 0), 1)) * right_Dimple) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DimpleL = ((left_Dimple * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%DimpleR = ((right_Dimple * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Frown_WrinkleNoseL = (((1 - (min(max(left_BrowInV + 1, 0), 1))) * left_Frown) * (1 - left_BrowOutV)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Frown_WrinkleNoseR = (((1 - (min(max(right_BrowInV + 1, 0), 1))) * right_Frown) * (1 - right_BrowOutV)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FrownL = left_Frown
	%FrownR = right_Frown
	%InflateCheekL = ((((((min(max(left_CheekH, 0), 1)) * (1 - (min(max(JawV, 0), 1)))) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InflateCheekR = ((((((min(max(right_CheekH, 0), 1)) * (1 - (min(max(JawV, 0), 1)))) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_OuterSquintL = (left_OuterSquint * left_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_OuterSquintR = (right_OuterSquint * right_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquintL = left_InnerSquint
	%InnerSquintR = right_InnerSquint
	%JutJaw = (min(max(JawD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLip_RaiseChinL = ((((1 - (min(max(left_LipLoV + 1, 0), 1))) * (1 - (min(max(left_LipUpV + 1, 0), 1)))) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLip_RaiseChinR = ((((1 - (min(max(right_LipLoV + 1, 0), 1))) * (1 - (min(max(right_LipUpV + 1, 0), 1)))) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLipL = ((1 - (min(max(left_LipUpV + 1, 0), 1))) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLipR = ((1 - (min(max(right_LipUpV + 1, 0), 1))) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwst_OpenUpperLip_SuckLipLoL = (((((1 - (min(max(left_FoldLipLo + 1, 0), 1))) * (min(max(left_LipUpV, 0), 1)) * left_LipCnrTwst) * (1 - left_Platysmus)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwst_OpenUpperLip_SuckLipLoR = (((((1 - (min(max(right_FoldLipLo + 1, 0), 1))) * (min(max(right_LipUpV, 0), 1)) * right_LipCnrTwst) * (1 - right_Platysmus)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwstL = (left_LipCnrTwst * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%LipCnrTwstR = (right_LipCnrTwst * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLipsL = (((min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLipsR = (((min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLip_Platysmus_SmileFullL = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLip_Platysmus_SmileFullR = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLipL = ((((min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLipR = ((((min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw = (min(max(JawV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLipsL = ((min(max(left_LipsV, 0), 1)) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLipsR = ((min(max(right_LipsV, 0), 1)) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLip_Platysmus_SmileFullL = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLip_Platysmus_SmileFullR = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLipL = ((((min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLipR = ((((min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SuckLipLoL = ((((1 - (min(max(left_FoldLipLo + 1, 0), 1))) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SuckLipLoR = ((((1 - (min(max(right_FoldLipLo + 1, 0), 1))) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLipL = ((min(max(left_LipLoV, 0), 1)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLipR = ((min(max(right_LipLoV, 0), 1)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SuckLipUpL = (((((1 - (min(max(left_FoldLipUp + 1, 0), 1))) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SuckLipUpR = (((((1 - (min(max(right_FoldLipUp + 1, 0), 1))) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLipL = ((min(max(left_LipUpV, 0), 1)) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLipR = ((min(max(right_LipUpV, 0), 1)) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OuterSquintL = left_OuterSquint
	%OuterSquintR = right_OuterSquint
	%PlatysmusL = left_Platysmus
	%PlatysmusR = right_Platysmus
	%PressNoseL = (1 - (min(max(left_NoseV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PressNoseR = (1 - (min(max(right_NoseV + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseBrowInL = (min(max(left_BrowInV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseBrowInR = (min(max(right_BrowInV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseChinL = ((1 - (min(max(left_LipLoV + 1, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%RaiseChinR = ((1 - (min(max(right_LipLoV + 1, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpBackL = (1 - (min(max(left_ScalpD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpBackR = (1 - (min(max(right_ScalpD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpForwardL = (min(max(left_ScalpD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%ScalpForwardR = (min(max(right_ScalpD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFlatL = ((((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFlatR = ((((((((min(1, (-min(0, (-11 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - -10))))) * min(max((multi_Smile - -11) / (-10 - -11), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - -10)))) - 1) * -(min(1, (-min(0, (-1 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * (1 - (min(max((multi_Smile - -1) / (0 - -1), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFullL = ((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileFullR = ((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileSharpL = ((((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (left_Smile)) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SmileSharpR = ((((((((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * min(max((multi_Smile - 0) / (1 - 0), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 1)))) - 1) * -(min(1, (-min(0, (10 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (10 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 11))))) * (1 - (min(max((multi_Smile - 10) / (11 - 10), 0), 1))))) * (right_Smile)) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SneerNoseL = (min(max(left_NoseV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SneerNoseR = (min(max(right_NoseV, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckJaw = (1 - (min(max(JawD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipLoL = ((1 - (min(max(left_FoldLipLo + 1, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipLoR = ((1 - (min(max(right_FoldLipLo + 1, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipUpL = (((1 - (min(max(left_FoldLipUp + 1, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckLipUpR = (((1 - (min(max(right_FoldLipUp + 1, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - ((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckNostrilL = (1 - (min(max(left_NostrilFlare + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SuckNostrilR = (1 - (min(max(right_NostrilFlare + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%WrinkleNoseL = ((1 - (min(max(left_BrowInV + 1, 0), 1))) * (1 - left_BrowOutV)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%WrinkleNoseR = ((1 - (min(max(right_BrowInV + 1, 0), 1))) * (1 - right_BrowOutV)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueBack = (min(max(TongueD, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlDown = (1 - (min(max(TongueCurl + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlUp = (min(max(TongueCurl, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueFunnel = TongueFunnel
	%TongueLeft = (min(max(TongueH, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueNarrow = (1 - (min(max(TongueWidth + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueOut = (1 - (min(max(TongueD + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueRight = (1 - (min(max(TongueH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueV = TongueV
	%TongueWide = (min(max(TongueWidth, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_OuterSquintL = (left_OuterSquint * left_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_OuterSquintR = (right_OuterSquint * right_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_InnerSquintL = (left_InnerSquint * left_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_InnerSquintR = (right_InnerSquint * right_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_InnerSquint_OuterSquintL = (left_OuterSquint * left_InnerSquint * left_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_InnerSquint_OuterSquintR = (right_OuterSquint * right_InnerSquint * right_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_InnerSquintL = (left_InnerSquint * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_InnerSquintR = (right_InnerSquint * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_OuterSquintL = (left_OuterSquint * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_OuterSquintR = (right_OuterSquint * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_InnerSquint_OuterSquintL = (left_OuterSquint * left_InnerSquint * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_InnerSquint_OuterSquintR = (right_OuterSquint * right_InnerSquint * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * left_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * right_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Frown_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * left_Frown) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Frown_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * right_Frown) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_CloseLidLoL = ((min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) * left_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_CloseLidLoR = ((min(1, (1 - (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (1 - (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1))) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) * right_CheekV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_OuterSquintL = (left_OuterSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_OuterSquintR = (right_OuterSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_InnerSquintL = (left_InnerSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_InnerSquintR = (right_InnerSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_InnerSquint_OuterSquintL = (left_OuterSquint * left_InnerSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_InnerSquint_OuterSquintR = (right_OuterSquint * right_InnerSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_OuterSquint_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * left_OuterSquint * left_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_OuterSquint_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * right_OuterSquint * right_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_InnerSquint_OuterSquint_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * left_OuterSquint * left_InnerSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CloseLidUp_InnerSquint_OuterSquint_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * right_OuterSquint * right_InnerSquint * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_CloseLidUpL = ((min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_CloseLidUpR = ((min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_FrownL = (left_Frown * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_FrownR = (right_Frown * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_CloseLidUp_RaiseBrowInL = ((min(max(left_BrowInV, 0), 1)) * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_CloseLidUp_RaiseBrowInR = ((min(max(right_BrowInV, 0), 1)) * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_CloseLidUp_FrownL = (left_Frown * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((left_CloseLid - -1) / (1 - -1), 0), 1))) * left_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%BrowOutV_CloseLidUp_FrownR = (right_Frown * (min(1, (1 + (-1 + 2 * (min(max((eyes_updown - -45) / (45 - -45), 0), 1))))) * (min(max((multi_CloseLid - -1) / (1 - -1), 0), 1)) * (min(max((right_CloseLid - -1) / (1 - -1), 0), 1))) * right_BrowOutV) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_SneerNoseL = ((min(max(left_NoseV, 0), 1)) * left_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_SneerNoseR = ((min(max(right_NoseV, 0), 1)) * right_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_OuterSquint_SneerNoseL = ((min(max(left_NoseV, 0), 1)) * left_OuterSquint * left_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%InnerSquint_OuterSquint_SneerNoseR = ((min(max(right_NoseV, 0), 1)) * right_OuterSquint * right_InnerSquint) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUpL = (left_PuckerLipUp * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUpR = (right_PuckerLipUp * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLoL = (left_PuckerLipLo * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLoR = (right_PuckerLipLo * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLo_PuckerLipUpL = (((left_PuckerLipUp * left_PuckerLipLo) * (1 - left_Platysmus)) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipLo_PuckerLipUpR = (((right_PuckerLipUp * right_PuckerLipLo) * (1 - right_Platysmus)) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PuckerLipUpL = ((left_PuckerLipUp * (min(max(JawV, 0), 1))) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PuckerLipUpR = ((right_PuckerLipUp * (min(max(JawV, 0), 1))) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PuckerLipLoL = ((left_PuckerLipLo * (min(max(JawV, 0), 1))) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PuckerLipLoR = ((right_PuckerLipLo * (min(max(JawV, 0), 1))) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PuckerLipLo_PuckerLipUpL = (((left_PuckerLipUp * left_PuckerLipLo * (min(max(JawV, 0), 1))) * (1 - left_Platysmus)) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PuckerLipLo_PuckerLipUpR = (((right_PuckerLipUp * right_PuckerLipLo * (min(max(JawV, 0), 1))) * (1 - right_Platysmus)) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_PuckerLipUpL = (((left_PuckerLipUp * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_PuckerLipUpR = (((right_PuckerLipUp * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_PuckerLipLoL = (((left_PuckerLipLo * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_PuckerLipLoR = (((right_PuckerLipLo * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_PuckerLipLo_PuckerLipUpL = ((((left_PuckerLipUp * left_PuckerLipLo * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_PuckerLipLo_PuckerLipUpR = ((((right_PuckerLipUp * right_PuckerLipLo * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_PuckerLipLo_PuckerLipUpL = ((((left_PuckerLipUp * left_PuckerLipLo * (min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_PuckerLipLo_PuckerLipUpR = ((((right_PuckerLipUp * right_PuckerLipLo * (min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_PuckerLipLoL = (((left_PuckerLipLo * (min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_PuckerLipLoR = (((right_PuckerLipLo * (min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_PuckerLipUpL = (((left_PuckerLipUp * (min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_PuckerLipUpR = (((right_PuckerLipUp * (min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_PuckerLipLoL = ((((left_PuckerLipLo * left_Dimple) * (1 - left_Platysmus)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_PuckerLipLoR = ((((right_PuckerLipLo * right_Dimple) * (1 - right_Platysmus)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_PuckerLipUpL = ((((left_PuckerLipUp * left_Dimple) * (1 - left_Platysmus)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_PuckerLipUpR = ((((right_PuckerLipUp * right_Dimple) * (1 - right_Platysmus)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_PuckerLipLo_PuckerLipUpL = (((((left_PuckerLipUp * left_PuckerLipLo * left_Dimple) * (1 - left_Platysmus)) * (1 - left_Platysmus)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_PuckerLipLo_PuckerLipUpR = (((((right_PuckerLipUp * right_PuckerLipLo * right_Dimple) * (1 - right_Platysmus)) * (1 - right_Platysmus)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_OpenLips_PuckerLipLo_PuckerLipUpL = ((((((left_PuckerLipUp * left_PuckerLipLo * (min(max(left_LipsV, 0), 1)) * left_Dimple) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_Platysmus)) * (1 - left_Platysmus)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_OpenLips_PuckerLipLo_PuckerLipUpR = ((((((right_PuckerLipUp * right_PuckerLipLo * (min(max(right_LipsV, 0), 1)) * right_Dimple) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_Platysmus)) * (1 - right_Platysmus)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUpL = ((((min(max(left_FoldLipUp, 0), 1)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUpR = ((((min(max(right_FoldLipUp, 0), 1)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLoL = ((((min(max(left_FoldLipLo, 0), 1)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLoR = ((((min(max(right_FoldLipLo, 0), 1)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLo_FunnelLipUpL = ((((((((min(max(left_FoldLipUp, 0), 1)) * (min(max(left_FoldLipLo, 0), 1))) * (1 - left_Platysmus)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLo_FunnelLipUpR = ((((((((min(max(right_FoldLipUp, 0), 1)) * (min(max(right_FoldLipLo, 0), 1))) * (1 - right_Platysmus)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_FunnelLipLoL = (((((((min(max(left_FoldLipLo, 0), 1)) * left_Dimple) * (1 - left_Platysmus)) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_FunnelLipLoR = (((((((min(max(right_FoldLipLo, 0), 1)) * right_Dimple) * (1 - right_Platysmus)) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_FunnelLipUpL = (((((((min(max(left_FoldLipUp, 0), 1)) * left_Dimple) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_FunnelLipUpR = (((((((min(max(right_FoldLipUp, 0), 1)) * right_Dimple) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_FunnelLipLo_FunnelLipUpL = ((((((((((min(max(left_FoldLipUp, 0), 1)) * (min(max(left_FoldLipLo, 0), 1)) * left_Dimple) * (1 - left_Platysmus)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) * (1 - left_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Dimple_FunnelLipLo_FunnelLipUpR = ((((((((((min(max(right_FoldLipUp, 0), 1)) * (min(max(right_FoldLipLo, 0), 1)) * right_Dimple) * (1 - right_Platysmus)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) * (1 - right_LipCnrTwst)) * (1 - (min(max(JawV, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUp_OpenJawL = (((((min(max(JawV, 0), 1)) * (min(max(left_FoldLipUp, 0), 1))) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipUp_OpenJawR = (((((min(max(JawV, 0), 1)) * (min(max(right_FoldLipUp, 0), 1))) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLo_OpenJawL = (((((min(max(JawV, 0), 1)) * (min(max(left_FoldLipLo, 0), 1))) * (1 - left_Platysmus)) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLo_OpenJawR = (((((min(max(JawV, 0), 1)) * (min(max(right_FoldLipLo, 0), 1))) * (1 - right_Platysmus)) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLo_FunnelLipUp_OpenJawL = ((((((((min(max(JawV, 0), 1)) * (min(max(left_FoldLipUp, 0), 1)) * (min(max(left_FoldLipLo, 0), 1))) * (1 - left_Platysmus)) * (1 - left_Platysmus)) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipLo)) * (1 - (min(max(JawV, 0), 1)) * left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%FunnelLipLo_FunnelLipUp_OpenJawR = ((((((((min(max(JawV, 0), 1)) * (min(max(right_FoldLipUp, 0), 1)) * (min(max(right_FoldLipLo, 0), 1))) * (1 - right_Platysmus)) * (1 - right_Platysmus)) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipLo)) * (1 - (min(max(JawV, 0), 1)) * right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipUpL = (((((left_PuffLipUp * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipUpR = (((((right_PuffLipUp * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipLoL = (((((left_PuffLipLo * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuffLipLoR = (((((right_PuffLipLo * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUp_RaiseChin_SneerNoseL = (((((min(max(left_NoseV, 0), 1)) * (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp) * (1 - left_Platysmus)) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUp_RaiseChin_SneerNoseR = (((((min(max(right_NoseV, 0), 1)) * (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp) * (1 - right_Platysmus)) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUp_RaiseChinL = (((((1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp) * (1 - left_Platysmus)) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%PuckerLipUp_RaiseChinR = (((((1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp) * (1 - right_Platysmus)) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenUpperLipL = ((((min(max(left_LipUpV, 0), 1)) * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenUpperLipR = ((((min(max(right_LipUpV, 0), 1)) * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenLowerLipL = ((((min(max(left_LipLoV, 0), 1)) * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenLowerLipR = ((((min(max(right_LipLoV, 0), 1)) * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_OpenUpperLipL = ((((min(max(left_LipUpV, 0), 1)) * (min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_OpenUpperLipR = ((((min(max(right_LipUpV, 0), 1)) * (min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_OpenLowerLipL = ((((min(max(left_LipLoV, 0), 1)) * (min(max(left_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLips_OpenLowerLipR = ((((min(max(right_LipLoV, 0), 1)) * (min(max(right_LipsV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLipL = (((min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLipR = (((min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLipL = (((min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLipR = (((min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_PlatysmusL = ((left_Platysmus * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_PlatysmusR = ((right_Platysmus * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_PlatysmusL = ((left_Platysmus * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_PlatysmusR = ((right_Platysmus * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLip_PlatysmusL = (((left_Platysmus * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLip_PlatysmusR = (((right_Platysmus * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLip_SmileFullL = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_OpenUpperLip_SmileFullR = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenUpperLip_SmileFullL = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenUpperLip_SmileFullR = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenLowerLip_SmileFullL = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(left_LipsV, 0), 1))) * (1 - (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLips_OpenLowerLip_SmileFullR = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(right_LipsV, 0), 1))) * (1 - (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Platysmus_SmileFullL = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Platysmus_SmileFullR = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Platysmus_RaiseChinL = (((1 - (min(max(left_LipLoV + 1, 0), 1))) * left_Platysmus) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%Platysmus_RaiseChinR = (((1 - (min(max(right_LipLoV + 1, 0), 1))) * right_Platysmus) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLip_Platysmus_RaiseChinL = ((((1 - (min(max(left_LipLoV + 1, 0), 1))) * left_Platysmus * (1 - (min(max(left_LipUpV + 1, 0), 1)))) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%JutUpperLip_Platysmus_RaiseChinR = ((((1 - (min(max(right_LipLoV + 1, 0), 1))) * right_Platysmus * (1 - (min(max(right_LipUpV + 1, 0), 1)))) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_Platysmus_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(left_LipUpV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenUpperLip_Platysmus_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(right_LipUpV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_Platysmus_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(left_LipLoV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenLowerLip_Platysmus_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(right_LipLoV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PlatysmusL = (left_Platysmus * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_PlatysmusR = (right_Platysmus * (min(max(JawV, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_PlatysmusL = ((left_Platysmus * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_PlatysmusR = ((right_Platysmus * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_SmileFullL = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_SmileFullR = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_Platysmus_SmileFullL = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_Platysmus_SmileFullR = (((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLip_SmileFullL = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLip_SmileFullR = (((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_Platysmus_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_Platysmus_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_PlatysmusL = ((left_Platysmus * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_PlatysmusR = ((right_Platysmus * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipUp)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLip_PlatysmusL = (((left_Platysmus * (min(max(left_LipUpV, 0), 1)) * (min(max(left_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenLowerLip_OpenUpperLip_PlatysmusR = (((right_Platysmus * (min(max(right_LipUpV, 0), 1)) * (min(max(right_LipLoV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_Platysmus_SmileFullL = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (left_Smile)) * left_Platysmus * (min(max(left_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - left_PuckerLipLo)) * (1 - left_PuckerLipUp)) * (1 - left_PuckerLipUp)) * (1 - (min(max(left_FoldLipLo, 0), 1)))) * (1 - (min(max(left_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%OpenJaw_OpenUpperLip_Platysmus_SmileFullR = ((((((((((min(1, (-min(0, (-1 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 0))))) * min(max((multi_Smile - -1) / (0 - -1), 0), 1)) + (-(min(1, (-min(0, (multi_Smile - 0)))) - 1) * -(min(1, (-min(0, (0 - multi_Smile)))) - 1)) + ((min(1, (-min(0, (0 - multi_Smile)))) * min(1, (-min(0, (multi_Smile - 1))))) * (1 - (min(max((multi_Smile - 0) / (1 - 0), 0), 1))))) * (right_Smile)) * right_Platysmus * (min(max(right_LipUpV, 0), 1)) * (min(max(JawV, 0), 1))) * (1 - right_PuckerLipLo)) * (1 - right_PuckerLipUp)) * (1 - right_PuckerLipUp)) * (1 - (min(max(right_FoldLipLo, 0), 1)))) * (1 - (min(max(right_FoldLipUp, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SlideJawL = (min(max(JawH, 0), 1)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%SlideJawR = (1 - (min(max(JawH + 1, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_PuckerLipUp_RaiseChinL = (((((1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp * left_CheekV) * (1 - left_Platysmus)) * (1 - (min(max(left_LipsV, 0), 1)))) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CheekV_PuckerLipUp_RaiseChinR = (((((1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp * right_CheekV) * (1 - right_Platysmus)) * (1 - (min(max(right_LipsV, 0), 1)))) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLips_JutUpperLip_RaiseChinL = (((((((1 - (min(max(left_LipLoV + 1, 0), 1))) * (1 - (min(max(left_LipUpV + 1, 0), 1))) * (1 - (min(max(left_LipsV + 1, 0), 1)))) * (1 - (min(max(left_LipLoV, 0), 1)))) * (1 - (min(max(left_LipUpV, 0), 1)))) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) * (1 - (1 - (min(max(left_LipLoV + 1, 0), 1))) * left_PuckerLipUp)) * (1 - left_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%CompressLips_JutUpperLip_RaiseChinR = (((((((1 - (min(max(right_LipLoV + 1, 0), 1))) * (1 - (min(max(right_LipUpV + 1, 0), 1))) * (1 - (min(max(right_LipsV + 1, 0), 1)))) * (1 - (min(max(right_LipLoV, 0), 1)))) * (1 - (min(max(right_LipUpV, 0), 1)))) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) * (1 - (1 - (min(max(right_LipLoV + 1, 0), 1))) * right_PuckerLipUp)) * (1 - right_PuckerLipLo)) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueBack_TongueCurlDown_TongueV = (TongueV * (1 - (min(max(TongueCurl + 1, 0), 1))) * (min(max(TongueD, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueBack_TongueCurlDown = ((1 - (min(max(TongueCurl + 1, 0), 1))) * (min(max(TongueD, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueBack_TongueV = (TongueV * (min(max(TongueD, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlDown_TongueOut = ((1 - (min(max(TongueD + 1, 0), 1))) * (1 - (min(max(TongueCurl + 1, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlDown_TongueV = (TongueV * (1 - (min(max(TongueCurl + 1, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlUp_TongueOut_TongueV = (TongueV * (1 - (min(max(TongueD + 1, 0), 1))) * (min(max(TongueCurl, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlUp_TongueOut = ((1 - (min(max(TongueD + 1, 0), 1))) * (min(max(TongueCurl, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueCurlUp_TongueV = (TongueV * (min(max(TongueCurl, 0), 1))) // WARNING: Expression is an approximation of what can only be done via DMX file.
	%TongueOut_TongueV = (TongueV * (1 - (min(max(TongueD + 1, 0), 1)))) // WARNING: Expression is an approximation of what can only be done via DMX file.
}
$bodygroup "rocket"
{
	blank
	studio "soldier_rocket.smd"
}
$bodygroup "helmet"
{
	studio "helmet_bodygroup.smd"
	blank
	studio "helmet_damaged_bodygroup.smd"
}
$bodygroup "cast"
{
	blank
	studio "soldier_cast.smd"
}
$bodygroup "sling"
{
	blank
	studio "sling_bodygroup.smd"
}


$surfaceprop "flesh"

$contents "solid"
